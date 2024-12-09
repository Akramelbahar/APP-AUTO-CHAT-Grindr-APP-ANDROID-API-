package main

import (
	"crypto/tls"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gorilla/websocket"
)

const maxRetries = 3 // Max number of retries for socket connection

// Function to establish a WebSocket connection with retry logic
func connectWebSocket(url string, headers http.Header) (*websocket.Conn, error) {
	var err error

	// Retry loop with exponential backoff
	for retryCount := 0; retryCount < maxRetries; retryCount++ {
		// Configure the WebSocket dialer with TLS
		dialer := websocket.Dialer{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true}, // Skip TLS verification (not recommended in production)
		}

		// Attempt WebSocket connection
		conn, resp, err := dialer.Dial(url, headers)
		if err == nil {
			fmt.Println("Response Status:", resp.Status)
			return conn, nil // Connection successful
		}

		// Log the connection error and retry with exponential backoff
		fmt.Printf("Error connecting to WebSocket (retry %d/%d): %v\n", retryCount+1, maxRetries, err)

		// Exponential backoff: delay 2^retryCount seconds
		backoffDuration := time.Duration(1<<retryCount) * time.Second
		time.Sleep(backoffDuration)
	}

	// If the loop exits without a successful connection, return the error
	return nil, fmt.Errorf("failed to connect to WebSocket after %d retries: %v", maxRetries, err)
}

func main() {
	// Ensure the required arguments are provided
	if len(os.Args) < 4 {
		log.Fatalf("Usage: %s <Authorization> <Device-Info> <User-Agent>", os.Args[0])
	}

	url := "wss://grindr.mobi/v1/ws" // Use 'wss' for WebSocket over HTTPS

	// Set headers for the WebSocket connection
	headers := http.Header{}
	headers.Set("Authorization", os.Args[1])
	headers.Set("L-Time-Zone", "Africa/Casablanca")
	headers.Set("L-Grindr-Roles", "[]")
	headers.Set("L-Device-Info", os.Args[2])
	headers.Set("Accept", "application/json")
	headers.Set("User-Agent", os.Args[3])
	headers.Set("L-Locale", "en_US")
	headers.Set("Accept-Language", "en-US")
	headers.Set("Accept-Encoding", "gzip")

	// Establish WebSocket connection with retry logic
	conn, err := connectWebSocket(url, headers)
	if err != nil {
		log.Fatalf("Error establishing WebSocket connection: %v", err)
	}
	defer conn.Close()

	// Set a read deadline for the connection (to prevent stalling forever)
	conn.SetReadDeadline(time.Now().Add(60 * time.Second))

	// Track received messages
	messageCount := 0
	maxMessages := 3
	var receivedMessages []string

	// Continuously read messages from the WebSocket
	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			if websocket.IsCloseError(err, websocket.CloseNormalClosure) {
				fmt.Println("WebSocket connection closed normally.")
				break
			}
			log.Printf("Error reading message: %v", err)
			break
		}

		// Reset the read deadline after each successful message
		conn.SetReadDeadline(time.Now().Add(60 * time.Second))

		messageCount++
		fmt.Printf("Received message: %s\n", message)

		// Store the received message
		receivedMessages = append(receivedMessages, string(message))

		// Check if the message count has reached the limit
		if messageCount >= maxMessages {
			fmt.Println("Reached maximum message limit. Closing connection and writing messages to file...")

			// Write the received messages to a file
			err := writeMessagesToFile(receivedMessages)
			if err != nil {
				log.Fatalf("Error writing messages to file: %v", err)
			}

			// Send a close message to the server
			err = conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, "Client closing after max messages"))
			if err != nil {
				log.Fatalf("Error sending close message: %v", err)
			}

			// Optionally, wait for the server's close response
			_, _, err = conn.ReadMessage()
			if err != nil {
				if websocket.IsCloseError(err, websocket.CloseNormalClosure) {
					fmt.Println("WebSocket connection closed gracefully.")
				} else {
					log.Fatalf("Error reading close response: %v", err)
				}
			}
			break
		}
	}
}

// Function to write the received messages to a file
func writeMessagesToFile(messages []string) error {
	// Create or open the file
	file, err := os.Create("received_messages.txt")
	if err != nil {
		return err
	}
	defer file.Close()

	// Write each message to the file
	for _, message := range messages {
		_, err := file.WriteString(message + "\n")
		if err != nil {
			return err
		}
	}
	fmt.Println("Messages written to file: received_messages.txt")
	return nil
}
