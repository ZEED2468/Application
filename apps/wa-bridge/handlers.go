package main

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"
)

// Server holds shared dependencies for the HTTP handlers. It carries no domain
// state; the only stateful field is the optional whatsmeow client.
type Server struct {
	cfg  Config
	http *http.Client
	wa   *waClient // nil in FAKE mode
}

// --- request/response payloads -------------------------------------------------

type pushRequest struct {
	VAJID     string `json:"va_jid"`
	DossierID string `json:"dossier_id"`
	Text      string `json:"text"`
}

type pushResponse struct {
	BridgeMessageRef string `json:"bridge_message_ref"`
}

type simulateInboundRequest struct {
	VAJID       string `json:"va_jid"`
	InReplyToRef string `json:"in_reply_to_ref"`
	Text        string `json:"text"`
}

type replyPayload struct {
	VAJID        string `json:"va_jid"`
	InReplyToRef string `json:"in_reply_to_ref"`
	Text         string `json:"text"`
	TS           int64  `json:"ts"`
}

// --- handlers ------------------------------------------------------------------

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// handlePush receives a dossier/chatbot text from FastAPI and relays it to the
// VA's WhatsApp. In FAKE mode it only logs. Always returns an opaque ref.
func (s *Server) handlePush(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		http.Error(w, "read error", http.StatusBadRequest)
		return
	}

	// Verify HMAC on inbound from FastAPI, unless in FAKE mode.
	if !s.cfg.Fake {
		if !s.verifySignature(body, r.Header.Get("X-Bridge-Signature")) {
			http.Error(w, "invalid signature", http.StatusUnauthorized)
			return
		}
	}

	var req pushRequest
	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	if req.VAJID == "" || req.Text == "" {
		http.Error(w, "va_jid and text are required", http.StatusBadRequest)
		return
	}

	ref := newRef()

	if s.cfg.Fake || s.wa == nil {
		log.Printf("FAKE push -> va_jid=%s dossier_id=%s ref=%s text=%q", req.VAJID, req.DossierID, ref, req.Text)
	} else {
		waRef, err := s.wa.sendText(req.VAJID, req.Text)
		if err != nil {
			log.Printf("push send failed va_jid=%s: %v", req.VAJID, err)
			http.Error(w, "send failed", http.StatusBadGateway)
			return
		}
		ref = waRef // prefer the real whatsmeow message id as the ref
		log.Printf("push sent -> va_jid=%s dossier_id=%s ref=%s", req.VAJID, req.DossierID, ref)
	}

	writeJSON(w, http.StatusOK, pushResponse{BridgeMessageRef: ref})
}

// handleSimulateInbound (FAKE mode only) pretends a VA replied on WhatsApp and
// drives the same outbound-to-FastAPI path a real inbound message would.
func (s *Server) handleSimulateInbound(w http.ResponseWriter, r *http.Request) {
	var req simulateInboundRequest
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	if req.VAJID == "" || req.Text == "" {
		http.Error(w, "va_jid and text are required", http.StatusBadRequest)
		return
	}

	if err := s.forwardReply(r.Context(), req.VAJID, req.InReplyToRef, req.Text); err != nil {
		log.Printf("simulate_inbound forward failed: %v", err)
		http.Error(w, "forward failed", http.StatusBadGateway)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "forwarded"})
}

// forwardReply POSTs a VA reply to FastAPI's bridge webhook, HMAC-signed. It is
// the single outbound path used by both real inbound events and simulation.
func (s *Server) forwardReply(ctx context.Context, vaJID, inReplyToRef, text string) error {
	payload := replyPayload{
		VAJID:        vaJID,
		InReplyToRef: inReplyToRef,
		Text:         text,
		TS:           time.Now().Unix(),
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal reply: %w", err)
	}

	url := s.cfg.APIBaseURL + "/api/webhooks/bridge/reply"
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-Bridge-Signature", s.sign(body))

	resp, err := s.http.Do(httpReq)
	if err != nil {
		return fmt.Errorf("post reply: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("fastapi returned %d: %s", resp.StatusCode, string(b))
	}
	log.Printf("forwarded reply -> va_jid=%s in_reply_to_ref=%s status=%d", vaJID, inReplyToRef, resp.StatusCode)
	return nil
}

// --- hmac ----------------------------------------------------------------------

func (s *Server) sign(body []byte) string {
	mac := hmac.New(sha256.New, s.cfg.HMACSecret)
	mac.Write(body)
	return hex.EncodeToString(mac.Sum(nil))
}

func (s *Server) verifySignature(body []byte, provided string) bool {
	want := s.sign(body)
	got, err := hex.DecodeString(provided)
	if err != nil {
		return false
	}
	wantBytes, _ := hex.DecodeString(want)
	return subtle.ConstantTimeCompare(wantBytes, got) == 1
}

// --- helpers -------------------------------------------------------------------

func newRef() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return "br_" + hex.EncodeToString(b)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
