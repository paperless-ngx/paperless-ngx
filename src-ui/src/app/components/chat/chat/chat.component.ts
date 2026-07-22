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
import { filter, map } from 'rxjs'
import {
  ChatMessage,
  ChatService,
  parseChatResponse,
} from 'src/app/services/chat.service'

@Component({
  selector: 'pngx-chat',
  imports: [
    FormsModule,
    ReactiveFormsModule,
    RouterModule,
    NgxBootstrapIconsModule,
    NgbDropdownModule,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent implements OnInit {
  readonly messages = signal<ChatMessage[]>([])
  readonly loading = signal(false)
  readonly input = signal('')
  readonly documentId = signal<number>(undefined)

  private chatService: ChatService = inject(ChatService)
  private router: Router = inject(Router)

  @ViewChild('scrollAnchor') scrollAnchor!: ElementRef<HTMLDivElement>
  @ViewChild('chatInput') chatInput!: ElementRef<HTMLInputElement>

  private typewriterBuffer: string[] = []
  private typewriterActive = false

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

    let lastVisibleContent = ''

    this.chatService.streamChat(this.documentId(), this.input()).subscribe({
      next: (chunk) => {
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
        assistantMessage.content += '\n\n⚠️ Error receiving response.'
        assistantMessage.isStreaming = false
        this.notifyMessagesChanged()
        this.loading.set(false)
      },
      complete: () => {
        assistantMessage.isStreaming = false
        this.notifyMessagesChanged()
        this.loading.set(false)
        this.scrollToBottom()
      },
    })

    this.input.set('')
  }

  private resetTypewriter(message: ChatMessage, content: string): void {
    this.typewriterBuffer = []
    this.typewriterActive = false
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
      return
    }

    const nextChar = this.typewriterBuffer.shift()
    message.content += nextChar
    this.notifyMessagesChanged()
    this.scrollToBottom()

    setTimeout(() => this.playTypewriter(message), 10) // 10ms per character
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
