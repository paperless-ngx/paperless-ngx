import { CommonModule } from '@angular/common'
import { HttpClient } from '@angular/common/http'
import { Component, ElementRef, OnInit, ViewChild } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { environment } from 'src/environments/environment'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'

interface ChatMessage {
  text: string
  fromUser: boolean
}

interface AiResponse {
  reply: string
  document_ids: string[]
  session_id: string
}

@Component({
  selector: 'app-ai-chat-widget',
  templateUrl: './ai-chat-widget.component.html',
  styleUrls: ['./ai-chat-widget.component.scss'],
  imports: [FormsModule, WidgetFrameComponent, CommonModule],
})
export class AiChatWidgetComponent implements OnInit {
  @ViewChild('chatContainer', { static: false }) chatContainer: ElementRef
  messages: ChatMessage[] = []
  currentMessage = ''
  showTypingAnimation = false
  sessionId: string | null = null

  constructor(private http: HttpClient) { }

  ngOnInit() {
    // Try to load session ID from localStorage
    this.sessionId = localStorage.getItem('paperless_chat_session_id')
  }

  sendMessage() {
    if (this.currentMessage.trim() === '') {
      return
    }

    // Add the user's message to the chat
    this.messages.push({
      text: this.currentMessage,
      fromUser: true,
    })
    // Scroll the chat container to the bottom
    this.scrollToBottom()

    // Send the message to a chatbot API and display the response
    const apiUrl = `${environment.apiBaseUrl}question/`
    const requestBody = {
      question: this.currentMessage,
      session_id: this.sessionId || undefined  // Only send if it exists
    }
    const headers = {
      Authorization:
        'Bearer ' +
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzNTYzNDU2NyIsIm5hbWUiOiJKb3NjaGthIiwiaWF0IjoxNTE2MjM5MDIyfQ.iecqerProyQ4OyhjzyMtHEb869b3Vbitp_T5tkip2Z4',
    }
    this.showTypingAnimation = true // show the typing animation
    this.http
      .post<AiResponse>(apiUrl, requestBody, { headers })
      .subscribe({
        next: (response: AiResponse) => {
          this.showTypingAnimation = false // hide the typing animation

          // Save the session ID for future messages
          this.sessionId = response.session_id
          localStorage.setItem('paperless_chat_session_id', response.session_id)

          // Add the chatbot's response to the chat
          this.messages.push({
            text: response.reply,
            fromUser: false,
          })
          // Scroll the chat container to the bottom
          this.scrollToBottom()
        },
        error: (error) => {
          this.showTypingAnimation = false
          console.error('Error sending message:', error)
          // Add error message to chat
          this.messages.push({
            text: 'Sorry, there was an error processing your message. Please try again.',
            fromUser: false,
          })
          this.scrollToBottom()
        }
      })

    // Clear the input field
    this.currentMessage = ''
  }

  clearChatHistory() {
    if (!this.sessionId) {
      return
    }

    const apiUrl = `${environment.apiBaseUrl}clear_chat_history/`
    const requestBody = { session_id: this.sessionId }
    const headers = {
      Authorization:
        'Bearer ' +
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzNTYzNDU2NyIsIm5hbWUiOiJKb3NjaGthIiwiaWF0IjoxNTE2MjM5MDIyfQ.iecqerProyQ4OyhjzyMtHEb869b3Vbitp_T5tkip2Z4',
    }

    this.http.post(apiUrl, requestBody, { headers }).subscribe(
      () => {
        // Clear the local messages
        this.messages = []
        // Keep the session ID, but clear the history in Redis
      },
      (error) => {
        console.error('Failed to clear chat history:', error)
      }
    )
  }

  private scrollToBottom() {
    setTimeout(() => {
      if (this.chatContainer) {
        this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight
      }
    })
  }
}
