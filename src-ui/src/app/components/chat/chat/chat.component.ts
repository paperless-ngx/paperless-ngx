import { Component, ElementRef, ViewChild } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ChatMessage, ChatService } from 'src/app/services/chat.service'

@Component({
  selector: 'pngx-chat',
  imports: [
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
    NgbDropdownModule,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent {
  messages: ChatMessage[] = []
  loading = false
  documentId = 295 // Replace this with actual doc ID logic
  input: string = ''
  @ViewChild('scrollAnchor') scrollAnchor!: ElementRef<HTMLDivElement>
  @ViewChild('inputField') inputField!: ElementRef<HTMLInputElement>

  private typewriterBuffer: string[] = []
  private typewriterActive = false

  constructor(private chatService: ChatService) {}

  sendMessage(): void {
    if (!this.input.trim()) return

    const userMessage: ChatMessage = { role: 'user', content: this.input }
    this.messages.push(userMessage)

    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      isStreaming: true,
    }
    this.messages.push(assistantMessage)
    this.loading = true

    let lastPartialLength = 0

    this.chatService.streamChat(this.documentId, this.input).subscribe({
      next: (chunk) => {
        const delta = chunk.substring(lastPartialLength)
        lastPartialLength = chunk.length
        this.enqueueTypewriter(delta, assistantMessage)
      },
      error: () => {
        assistantMessage.content += '\n\n⚠️ Error receiving response.'
        assistantMessage.isStreaming = false
        this.loading = false
      },
      complete: () => {
        assistantMessage.isStreaming = false
        this.loading = false
        this.scrollToBottom()
      },
    })

    this.input = ''
  }

  enqueueTypewriter(chunk: string, message: ChatMessage): void {
    if (!chunk) return

    this.typewriterBuffer.push(...chunk.split(''))

    if (!this.typewriterActive) {
      this.typewriterActive = true
      this.playTypewriter(message)
    }
  }

  playTypewriter(message: ChatMessage): void {
    if (this.typewriterBuffer.length === 0) {
      this.typewriterActive = false
      return
    }

    const nextChar = this.typewriterBuffer.shift()!
    message.content += nextChar
    this.scrollToBottom()

    setTimeout(() => this.playTypewriter(message), 10) // 10ms per character
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      this.scrollAnchor?.nativeElement?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
  }

  public onOpenChange(open: boolean): void {
    if (open) {
      setTimeout(() => {
        this.inputField.nativeElement.focus()
      }, 10)
    }
  }

  public searchInputKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault()
      this.sendMessage()
    }
    // } else if (event.key === 'Escape' && !this.resultsDropdown.isOpen()) {
    //   if (this.query?.length) {
    //     this.reset(true)
    //   } else {
    //     this.searchInput.nativeElement.blur()
    //   }
    // }
  }
}
