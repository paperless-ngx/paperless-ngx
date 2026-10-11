import {
  AfterViewChecked,
  Component,
  ElementRef,
  HostListener,
  inject,
  OnInit,
  signal,
  ViewChild,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NavigationEnd, Router, RouterModule } from '@angular/router'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import katex from 'katex'
import { filter, map } from 'rxjs'
import { ChatMarkdownPipe } from 'src/app/pipes/chat-markdown.pipe'
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
    ChatMarkdownPipe,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent implements OnInit, AfterViewChecked {
  readonly messages = signal<ChatMessage[]>([])
  readonly loading = signal(false)
  readonly input = signal('')
  readonly documentId = signal<number>(undefined)
  readonly isOpen = signal(false)

  private readonly chatService: ChatService = inject(ChatService)
  private readonly router: Router = inject(Router)
  private readonly host = inject(ElementRef<HTMLElement>)

  @ViewChild('scrollAnchor') scrollAnchor!: ElementRef<HTMLDivElement>
  @ViewChild('chatInput') chatInput!: ElementRef<HTMLInputElement>

  private typewriterBuffer: string[] = []
  private typewriterActive = false

  public get placeholder(): string {
    return this.documentId()
      ? $localize`Ask a question about this document...`
      : $localize`Ask a question about a document...`
  }

  public get contextDescription(): string {
    return this.documentId()
      ? $localize`Asking about this document`
      : $localize`Searching your accessible documents`
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

  ngAfterViewChecked(): void {
    this.host.nativeElement
      .querySelectorAll<HTMLElement>('.chat-math[title]')
      .forEach((element) => {
        const encodedFormula = element.getAttribute('title')
        if (!encodedFormula) return

        try {
          katex.render(decodeURIComponent(encodedFormula), element, {
            displayMode: element.classList.contains('chat-math-display'),
            throwOnError: false,
            trust: false,
          })
        } catch {
          element.textContent = ''
        }
        element.removeAttribute('title')
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

  public togglePanel(): void {
    if (this.isOpen()) {
      this.closePanel()
    } else {
      this.isOpen.set(true)
      setTimeout(() => {
        this.chatInput.nativeElement.focus()
      }, 10)
    }
  }

  public closePanel(): void {
    this.isOpen.set(false)
  }

  @HostListener('document:keydown.escape')
  public onEscape(): void {
    if (this.isOpen()) {
      this.closePanel()
    }
  }

  public searchInputKeyDown(event: KeyboardEvent): void {
    if (
      event.key === 'Enter' &&
      !event.shiftKey &&
      !(event.isComposing || event.keyCode === 229)
    ) {
      event.preventDefault()
      this.sendMessage()
    }
  }
}
