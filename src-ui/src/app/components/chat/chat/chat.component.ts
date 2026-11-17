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
import { filter, map, Subscription } from 'rxjs'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { MarkdownPipe } from 'src/app/pipes/markdown.pipe'
import {
  ChatMessage,
  ChatReference,
  ChatService,
  parseChatResponse,
} from 'src/app/services/chat.service'
import { pngxPopperOptions } from 'src/app/utils/popper-options'

const SLOW_RESPONSE_DELAY_MS = 8000
const TYPEWRITER_MIN_DURATION_MS = 750
const TYPEWRITER_MAX_DURATION_MS = 3000
const TYPEWRITER_INTERVAL_MS = 16

@Component({
  selector: 'pngx-chat',
  imports: [
    FormsModule,
    ReactiveFormsModule,
    RouterModule,
    BootstrapIconComponent,
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
  readonly expandedReferences = signal<Set<ChatMessage>>(new Set())
  public popperOptions = pngxPopperOptions

  static readonly COLLAPSED_REFERENCE_COUNT = 2

  public visibleReferences(message: ChatMessage): ChatReference[] {
    if (this.expandedReferences().has(message)) {
      return message.references
    }
    return message.references.slice(0, ChatComponent.COLLAPSED_REFERENCE_COUNT)
  }

  public hiddenReferenceCount(message: ChatMessage): number {
    return Math.max(
      0,
      message.references.length - ChatComponent.COLLAPSED_REFERENCE_COUNT
    )
  }

  public expandReferences(message: ChatMessage): void {
    this.expandedReferences.update((expanded) => new Set(expanded).add(message))
  }

  private chatService: ChatService = inject(ChatService)
  private router: Router = inject(Router)

  @ViewChild('scrollAnchor') scrollAnchor!: ElementRef<HTMLDivElement>
  @ViewChild('chatInput') chatInput!: ElementRef<HTMLInputElement>

  private typewriterBuffer: string[] = []
  private typewriterActive = false
  private typewriterTimeout: ReturnType<typeof setTimeout>
  private typewriterDeadline = 0
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
          } else if (nextResponse.content.length > lastVisibleContent.length) {
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

  clearChat(): void {
    this.stopStreaming()
    this.messages.set([])
    setTimeout(() => this.chatInput?.nativeElement.focus())
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
    // Longer bursts need more time to remain readable as the chat scrolls.
    const revealDuration = Math.min(
      TYPEWRITER_MAX_DURATION_MS,
      Math.max(TYPEWRITER_MIN_DURATION_MS, this.typewriterBuffer.length)
    )
    this.typewriterDeadline = Date.now() + revealDuration

    if (!this.typewriterActive) {
      this.typewriterActive = true
      this.playTypewriter(message)
    }
  }

  playTypewriter(message: ChatMessage): void {
    // Spread the queued text across the updates left before the deadline
    const remainingUpdates = Math.max(
      1,
      Math.ceil((this.typewriterDeadline - Date.now()) / TYPEWRITER_INTERVAL_MS)
    )
    const charactersToShow = Math.ceil(
      this.typewriterBuffer.length / remainingUpdates
    )
    message.content += this.typewriterBuffer
      .splice(0, charactersToShow)
      .join('')
    this.notifyMessagesChanged()
    this.scrollToBottom()

    if (this.typewriterBuffer.length === 0) {
      this.typewriterActive = false
      if (this.streamFinished) this.finishStreaming(message)
    } else {
      this.typewriterTimeout = setTimeout(
        () => this.playTypewriter(message),
        TYPEWRITER_INTERVAL_MS
      )
    }
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
