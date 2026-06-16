// Command wa-bridge is a dumb transport pipe between the JD FastAPI backend and
// a VA's WhatsApp. It holds no business logic and no domain state — only the
// whatsmeow session. All decisions live in the FastAPI backend.
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

// Config is the full runtime configuration, loaded from environment variables.
type Config struct {
	Port           string
	APIBaseURL     string
	HMACSecret     []byte
	Fake           bool
	SessionDir     string
}

func loadConfig() Config {
	return Config{
		Port:       env("PORT", "8081"),
		APIBaseURL: env("API_BASE_URL", "http://localhost:8000"),
		HMACSecret: []byte(env("BRIDGE_HMAC_SECRET", "dev-bridge-secret")),
		Fake:       env("BRIDGE_FAKE", "1") == "1",
		SessionDir: env("WHATSAPP_SESSION_DIR", "./session"),
	}
}

func env(key, def string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return def
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmsgprefix)
	log.SetPrefix("[wa-bridge] ")

	cfg := loadConfig()

	srv := &Server{cfg: cfg, http: &http.Client{Timeout: 15 * time.Second}}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if cfg.Fake {
		log.Printf("starting in FAKE mode (whatsmeow disabled); API_BASE_URL=%s port=%s", cfg.APIBaseURL, cfg.Port)
	} else {
		log.Printf("starting in REAL mode; session=%s API_BASE_URL=%s port=%s", cfg.SessionDir, cfg.APIBaseURL, cfg.Port)
		if err := srv.startWhatsApp(ctx); err != nil {
			log.Fatalf("whatsapp init failed: %v", err)
		}
		defer srv.stopWhatsApp()
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", srv.handleHealth)
	mux.HandleFunc("POST /push", srv.handlePush)
	if cfg.Fake {
		mux.HandleFunc("POST /_simulate_inbound", srv.handleSimulateInbound)
	}

	httpServer := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}

	go func() {
		log.Printf("listening on :%s", cfg.Port)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("http server error: %v", err)
		}
	}()

	<-ctx.Done()
	log.Printf("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(shutdownCtx)
}
