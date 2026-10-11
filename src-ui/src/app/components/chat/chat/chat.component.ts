import {
  Component,
  ElementRef,
  inject,
  OnInit,
  signal,
  ViewChild,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NavigationEnd, Router, RouterModule } from '@angular/router'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { filter, map, Subscription } from 'rxjs'
import { MarkdownPipe } from 'src/app/pipes/markdown.pipe'
import {
  ChatMessage,
  ChatService,
  parseChatResponse,
} from 'src/app/services/chat.service'
import { pngxPopperOptions } from 'src/app/utils/popper-options'

const SLOW_RESPONSE_DELAY_MS = 8000

@Component({
  selector: 'pngx-chat',
  imports: [
    FormsModule,
    ReactiveFormsModule,
    RouterModule,
    NgxBootstrapIconsModule,
    NgbDropdownModule,
    MarkdownPipe,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent implements OnInit {
  readonly messages = signal<ChatMessage[]>([])
  readonly loading = signal(false)
  readonly input = signal('')
  readonly documentId = signal<number>(undefined)
  readonly slowResponse = signal(false)
  public popperOptions = pngxPopperOptions

  private chatService: ChatService = inject(ChatService)
  private router: Router = inject(Router)

  @ViewChild('scrollAnchor') scrollAnchor!: ElementRef<HTMLDivElement>
  @ViewChild('chatInput') chatInput!: ElementRef<HTMLInputElement>

  private typewriterBuffer: string[] = []
  private typewriterActive = false
  private typewriterTimeout: ReturnType<typeof setTimeout>
  private streamSubscription: Subscription
  private streamingMessage: ChatMessage
  private streamFinished = false
  private slowResponseTimeout: ReturnType<typeof setTimeout>

  public get placeholder(): string {
    return this.documentId()
      ? $localize`Ask a question about this document...`
      : $localize`Ask a question about a document...`
  }

  ngOnInit(): void {
    this.updateDocumentId(this.router.url)
    this.router.events
      .pipe(
        filter((event) => event instanceof NavigationEnd),
        map((event) => (event as NavigationEnd).url)
      )
      .subscribe((url) => {
        this.updateDocumentId(url)
      })
  }

  private updateDocumentId(url: string): void {
    const docIdRe = url.match(/^\/documents\/(\d+)/)
    this.documentId.set(docIdRe ? +docIdRe[1] : undefined)
  }

  sendMessage(): void {
    if (!this.input().trim()) return

    const userMessage: ChatMessage = { role: 'user', content: this.input() }
    this.messages.update((messages) => [...messages, userMessage])
    this.scrollToBottom()

    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      isStreaming: true,
    }
    this.messages.update((messages) => [...messages, assistantMessage])
    this.loading.set(true)
    this.streamingMessage = assistantMessage
    this.streamFinished = false
    this.slowResponseTimeout = setTimeout(
      () => this.slowResponse.set(true),
      SLOW_RESPONSE_DELAY_MS
    )

    let lastVisibleContent = ''

    this.streamSubscription = this.chatService
      .streamChat(this.documentId(), this.input())
      .subscribe({
        next: (chunk) => {
          this.clearSlowResponse()
          const nextResponse = parseChatResponse(chunk)

          if (nextResponse.content.length < lastVisibleContent.length) {
            this.resetTypewriter(assistantMessage, nextResponse.content)
            lastVisibleContent = nextResponse.content
          } else {
            const visibleDelta = nextResponse.content.substring(
              lastVisibleContent.length
            )
            lastVisibleContent = nextResponse.content
            this.enqueueTypewriter(visibleDelta, assistantMessage)
          }

          assistantMessage.references = nextResponse.references
          this.notifyMessagesChanged()
        },
        error: () => {
          this.flushTypewriter(assistantMessage)
          assistantMessage.content += '\n\n⚠️ Error receiving response.'
          this.finishStreaming(assistantMessage)
        },
        complete: () => {
          // let the typewriter catch up before hiding the cursor
          this.streamFinished = true
          if (!this.typewriterActive) this.finishStreaming(assistantMessage)
        },
      })

    this.input.set('')
  }

  stopStreaming(): void {
    const message = this.streamingMessage
    if (!message?.isStreaming) return

    this.streamSubscription?.unsubscribe()
    this.flushTypewriter(message)
    if (!message.content) {
      this.messages.update((messages) => messages.filter((m) => m !== message))
    }
    this.finishStreaming(message)
  }

  private finishStreaming(message: ChatMessage): void {
    this.clearSlowResponse()
    this.streamFinished = false
    message.isStreaming = false
    this.notifyMessagesChanged()
    this.loading.set(false)
    this.scrollToBottom()
  }

  private clearSlowResponse(): void {
    clearTimeout(this.slowResponseTimeout)
    this.slowResponse.set(false)
  }

  private flushTypewriter(message: ChatMessage): void {
    message.content += this.typewriterBuffer.join('')
    this.cancelTypewriter()
  }

  private cancelTypewriter(): void {
    clearTimeout(this.typewriterTimeout)
    this.typewriterBuffer = []
    this.typewriterActive = false
  }

  private resetTypewriter(message: ChatMessage, content: string): void {
    this.cancelTypewriter()
    message.content = content
    this.notifyMessagesChanged()
    this.scrollToBottom()
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
      if (this.streamFinished) this.finishStreaming(message)
      return
    }

    const nextChar = this.typewriterBuffer.shift()
    message.content += nextChar
    this.notifyMessagesChanged()
    this.scrollToBottom()

    // 10ms per character
    this.typewriterTimeout = setTimeout(() => this.playTypewriter(message), 10)
  }

  private notifyMessagesChanged(): void {
    this.messages.update((messages) => [...messages])
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      this.scrollAnchor?.nativeElement?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
  }

  public onOpenChange(open: boolean): void {
    if (open) {
      setTimeout(() => {
        this.chatInput.nativeElement.focus()
      }, 10)
    }
  }

  public searchInputKeyDown(event: KeyboardEvent) {
    if (
      event.key === 'Enter' &&
      !(event.isComposing || event.keyCode === 229)
    ) {
      event.preventDefault()
      this.sendMessage()
    }
  }
}
