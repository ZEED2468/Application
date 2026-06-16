package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/mdp/qrterminal/v3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"

	_ "github.com/mattn/go-sqlite3"
)

// waClient wraps a connected whatsmeow client plus the backreference needed to
// forward inbound messages to FastAPI. It exists only when BRIDGE_FAKE != "1".
type waClient struct {
	client    *whatsmeow.Client
	container *sqlstore.Container
	srv       *Server
}

// startWhatsApp boots the whatsmeow client: opens the sqlite store, loads or
// pairs a device (printing a QR to stdout when unpaired), connects, and wires
// the inbound message handler. Only ever called outside FAKE mode.
func (s *Server) startWhatsApp(ctx context.Context) error {
	if err := os.MkdirAll(s.cfg.SessionDir, 0o755); err != nil {
		return fmt.Errorf("create session dir: %w", err)
	}
	dbPath := filepath.Join(s.cfg.SessionDir, "whatsmeow.db")
	dsn := "file:" + dbPath + "?_foreign_keys=on"

	dbLog := waLog.Stdout("store", "INFO", true)
	container, err := sqlstore.New(ctx, "sqlite3", dsn, dbLog)
	if err != nil {
		return fmt.Errorf("open sqlite store: %w", err)
	}

	device, err := container.GetFirstDevice(ctx)
	if err != nil {
		return fmt.Errorf("get device: %w", err)
	}

	clientLog := waLog.Stdout("client", "INFO", true)
	client := whatsmeow.NewClient(device, clientLog)

	wa := &waClient{client: client, container: container, srv: s}
	client.AddEventHandler(wa.handleEvent)
	s.wa = wa

	if client.Store.ID == nil {
		// Not paired yet: fetch a QR channel, then connect.
		qrChan, err := client.GetQRChannel(ctx)
		if err != nil {
			return fmt.Errorf("get qr channel: %w", err)
		}
		if err := client.Connect(); err != nil {
			return fmt.Errorf("connect: %w", err)
		}
		go func() {
			for evt := range qrChan {
				switch evt.Event {
				case "code":
					log.Printf("scan this QR with WhatsApp (Linked Devices):")
					qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
				case "success":
					log.Printf("whatsapp pairing successful")
				default:
					log.Printf("whatsapp qr event: %s", evt.Event)
				}
			}
		}()
	} else {
		if err := client.Connect(); err != nil {
			return fmt.Errorf("connect: %w", err)
		}
		log.Printf("whatsapp connected with existing session")
	}

	return nil
}

func (s *Server) stopWhatsApp() {
	if s.wa != nil && s.wa.client != nil {
		s.wa.client.Disconnect()
	}
}

// sendText sends a plain-text WhatsApp message and returns the whatsmeow
// message id, which the caller uses as the bridge_message_ref.
func (w *waClient) sendText(vaJID, text string) (string, error) {
	jid, err := types.ParseJID(vaJID)
	if err != nil {
		return "", fmt.Errorf("parse jid %q: %w", vaJID, err)
	}
	msg := &waE2E.Message{Conversation: proto.String(text)}
	resp, err := w.client.SendMessage(context.Background(), jid, msg)
	if err != nil {
		return "", fmt.Errorf("send message: %w", err)
	}
	return string(resp.ID), nil
}

// handleEvent forwards inbound text messages (from the VA) to FastAPI. Messages
// we sent ourselves are ignored. The bridge applies no logic beyond extracting
// the text and the sender JID.
func (w *waClient) handleEvent(evt any) {
	msg, ok := evt.(*events.Message)
	if !ok {
		return
	}
	if msg.Info.IsFromMe {
		return
	}

	text := extractText(msg.Message)
	if text == "" {
		return
	}

	vaJID := msg.Info.Sender.ToNonAD().String()
	if err := w.srv.forwardReply(context.Background(), vaJID, "", text); err != nil {
		log.Printf("inbound forward failed va_jid=%s: %v", vaJID, err)
	}
}

func extractText(m *waE2E.Message) string {
	if m == nil {
		return ""
	}
	if c := m.GetConversation(); c != "" {
		return c
	}
	if ext := m.GetExtendedTextMessage(); ext != nil {
		return ext.GetText()
	}
	return ""
}
