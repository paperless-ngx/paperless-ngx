import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ElementRef } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NavigationEnd, Router } from '@angular/router'
import { RouterTestingModule } from '@angular/router/testing'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import {
  CHAT_METADATA_DELIMITER,
  ChatService,
} from 'src/app/services/chat.service'
import { ChatComponent } from './chat.component'

describe('ChatComponent', () => {
  let component: ChatComponent
  let fixture: ComponentFixture<ChatComponent>
  let chatService: ChatService
  let router: Router
  let routerEvents$: Subject<NavigationEnd>
  let mockStream$: Subject<string>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgxBootstrapIconsModule.pick(allIcons),
        RouterTestingModule,
        ChatComponent,
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(ChatComponent)
    router = TestBed.inject(Router)
    routerEvents$ = new Subject<any>()
    jest
      .spyOn(router, 'events', 'get')
      .mockReturnValue(routerEvents$.asObservable())
    chatService = TestBed.inject(ChatService)
    mockStream$ = new Subject<string>()
    jest
      .spyOn(chatService, 'streamChat')
      .mockReturnValue(mockStream$.asObservable())
    component = fixture.componentInstance

    jest.useFakeTimers()

    fixture.detectChanges()

    component.scrollAnchor.nativeElement.scrollIntoView = jest.fn()
  })

  it('should update documentId on initialization', () => {
    jest.spyOn(router, 'url', 'get').mockReturnValue('/documents/123')
    component.ngOnInit()
    expect(component.documentId()).toBe(123)
  })

  it('should update documentId on navigation', () => {
    component.ngOnInit()
    routerEvents$.next(new NavigationEnd(1, '/documents/456', '/documents/456'))
    expect(component.documentId()).toBe(456)
  })

  it('should return correct placeholder based on documentId', () => {
    component.documentId.set(123)
    expect(component.placeholder).toBe('Ask a question about this document...')
    component.documentId.set(undefined)
    expect(component.placeholder).toBe('Ask a question about a document...')
  })

  it('should send a message and render the streaming response', async () => {
    component.input.set('Hello')
    component.sendMessage()

    expect(component.messages()).toHaveLength(2)
    expect(component.messages()[0].content).toBe('Hello')
    expect(component.loading()).toBe(true)

    fixture.detectChanges()
    const messagesEl = fixture.nativeElement.querySelector('.chat-messages')
    expect(messagesEl.querySelector('.spinner-border')).not.toBeNull()
    expect(messagesEl.textContent).toContain('Thinking...')

    mockStream$.next('Hi')
    expect(component.messages()[1].content).toBe('H')
    fixture.detectChanges()
    expect(messagesEl.querySelector('.spinner-border')).toBeNull()
    expect(messagesEl.querySelector('.chat-markdown.streaming')).not.toBeNull()
    mockStream$.next('Hi there')
    // advance time to process the typewriter effect
    await jest.runAllTimersAsync()
    await fixture.whenStable()
    expect(component.messages()[1].content).toBe('Hi there')
    expect(
      fixture.nativeElement.querySelector('.chat-messages').textContent
    ).toContain('Hi there')

    mockStream$.complete()
    await jest.runAllTimersAsync()
    await fixture.whenStable()
    expect(component.loading()).toBe(false)
    expect(component.messages()[1].isStreaming).toBe(false)
    fixture.detectChanges()
    expect(messagesEl.querySelector('.chat-markdown.streaming')).toBeNull()
    expect(fixture.nativeElement.querySelector('#chatInput').disabled).toBe(
      false
    )
  })

  it('should parse references from the metadata trailer without showing it', () => {
    component.input.set('Hello')
    component.sendMessage()

    mockStream$.next(
      `Hi there${CHAT_METADATA_DELIMITER}{"references":[{"id":42,"title":"Bread Recipe"}]}`
    )
    jest.advanceTimersByTime(1000)

    expect(component.messages()[1].content).toBe('Hi there')
    expect(component.messages()[1].references).toEqual([
      { id: 42, title: 'Bread Recipe' },
    ])
  })

  it('should render document reference links under assistant messages', () => {
    component.input.set('Hello')
    component.sendMessage()

    mockStream$.next(
      `Hi there${CHAT_METADATA_DELIMITER}{"references":[{"id":42,"title":"Bread Recipe"}]}`
    )
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelector('.chat-references')).toBeNull()

    mockStream$.complete()
    jest.advanceTimersByTime(1000)
    fixture.detectChanges()

    const link = fixture.nativeElement.querySelector('.chat-references a')
    expect(link.textContent).toContain('Bread Recipe')
    expect(link.getAttribute('href')).toContain('/documents/42')
  })

  it('should remove delimiter fragments that were already streamed', () => {
    component.input.set('Hello')
    component.sendMessage()

    mockStream$.next(`Hi there${CHAT_METADATA_DELIMITER.slice(0, 8)}`)
    jest.advanceTimersByTime(1000)
    expect(component.messages()[1].content).toBe(
      `Hi there${CHAT_METADATA_DELIMITER.slice(0, 8)}`
    )

    mockStream$.next(
      `Hi there${CHAT_METADATA_DELIMITER}{"references":[{"id":42,"title":"Bread Recipe"}]}`
    )
    jest.advanceTimersByTime(1000)

    expect(component.messages()[1].content).toBe('Hi there')
    expect(component.messages()[1].references).toEqual([
      { id: 42, title: 'Bread Recipe' },
    ])
  })

  it('should handle errors during streaming', () => {
    component.input.set('Hello')
    component.sendMessage()

    mockStream$.next('Partial')
    mockStream$.error('Error')
    expect(component.messages()[1].content).toBe(
      'Partial\n\n⚠️ Error receiving response.'
    )
    expect(component.loading()).toBe(false)
  })

  it('should keep streaming until the typewriter catches up', () => {
    component.input.set('Hello')
    component.sendMessage()

    mockStream$.next('Hi there')
    mockStream$.complete()
    expect(component.messages()[1].isStreaming).toBe(true)
    expect(component.loading()).toBe(true)

    jest.advanceTimersByTime(1000)
    expect(component.messages()[1].content).toBe('Hi there')
    expect(component.messages()[1].isStreaming).toBe(false)
    expect(component.loading()).toBe(false)
  })

  it('should show a slow response message while waiting', () => {
    component.input.set('Hello')
    component.sendMessage()
    fixture.detectChanges()
    const messagesEl = fixture.nativeElement.querySelector('.chat-messages')
    expect(messagesEl.textContent).not.toContain('Still thinking...')

    jest.advanceTimersByTime(8000)
    fixture.detectChanges()
    expect(messagesEl.textContent).toContain('Still thinking...')

    mockStream$.next('Hi')
    expect(component.slowResponse()).toBe(false)
  })

  it('should stop streaming and keep the partial response', () => {
    component.input.set('Hello')
    component.sendMessage()
    fixture.detectChanges()
    const stopButton = fixture.nativeElement.querySelector('.chat-input button')
    expect(stopButton.getAttribute('aria-label')).toBe('Stop')

    mockStream$.next('Hi there')
    jest.advanceTimersByTime(20)
    stopButton.click()

    expect(mockStream$.observed).toBe(false)
    expect(component.messages()[1].content).toBe('Hi there')
    expect(component.messages()[1].isStreaming).toBe(false)
    expect(component.loading()).toBe(false)

    jest.advanceTimersByTime(1000)
    expect(component.messages()[1].content).toBe('Hi there')
  })

  it('should drop the empty response when stopped before any content', () => {
    component.input.set('Hello')
    component.sendMessage()
    component.stopStreaming()

    expect(component.messages()).toHaveLength(1)
    expect(component.loading()).toBe(false)
    component.stopStreaming() // no-op once stopped
    expect(component.messages()).toHaveLength(1)
  })

  it('should clear the conversation', () => {
    component.input.set('Hello')
    component.sendMessage()
    mockStream$.next('Hi there')
    fixture.detectChanges()

    fixture.nativeElement.querySelector('button[title="Clear chat"]').click()
    expect(component.messages()).toHaveLength(0)
    expect(component.loading()).toBe(false)
    expect(mockStream$.observed).toBe(false)

    fixture.detectChanges()
    jest.advanceTimersByTime(10)
    expect(document.activeElement).toBe(
      fixture.nativeElement.querySelector('#chatInput')
    )
    expect(fixture.nativeElement.textContent).toContain(
      'Answers come from your documents'
    )
  })

  it('should enqueue typewriter chunks correctly', () => {
    const message = { content: '', role: 'assistant', isStreaming: true }
    component.enqueueTypewriter(null, message as any) // coverage for null
    component.enqueueTypewriter('Hello', message as any)
    expect(component['typewriterBuffer']).toHaveLength(4)
  })

  it('should scroll to bottom after sending a message', () => {
    const scrollSpy = jest.spyOn(
      ChatComponent.prototype as any,
      'scrollToBottom'
    )
    component.input.set('Test')
    component.sendMessage()
    expect(scrollSpy).toHaveBeenCalled()
  })

  it('should focus chat input when dropdown is opened', () => {
    const focus = jest.fn()
    component.chatInput = {
      nativeElement: { focus: focus },
    } as unknown as ElementRef<HTMLInputElement>

    component.onOpenChange(true)
    jest.advanceTimersByTime(15)
    expect(focus).toHaveBeenCalled()
  })

  it('should send message on Enter key press', () => {
    jest.spyOn(component, 'sendMessage')
    const event = new KeyboardEvent('keydown', { key: 'Enter' })
    component.searchInputKeyDown(event)
    expect(component.sendMessage).toHaveBeenCalled()
  })

  it('should not send message on Enter key press while composing with IME', () => {
    jest.spyOn(component, 'sendMessage')
    const event = new KeyboardEvent('keydown', {
      key: 'Enter',
      isComposing: true,
    })
    component.searchInputKeyDown(event)
    expect(component.sendMessage).not.toHaveBeenCalled()
  })

  it('should render markdown for assistant messages only', () => {
    component.messages.set([
      { role: 'user', content: '**user**' },
      { role: 'assistant', content: '**assistant** <script>x</script>' },
    ])
    fixture.detectChanges()
    const el: HTMLElement = fixture.nativeElement
    expect(el.querySelector('.chat-markdown strong')?.textContent).toBe(
      'assistant'
    )
    expect(el.querySelector('.chat-markdown script')).toBeNull()
    expect(el.textContent).toContain('**user**')
  })

  it('should keep the destination hostname visible after sanitizing chat links', () => {
    component.messages.set([
      {
        role: 'assistant',
        content:
          '[View original document](https://otherdomain.example/?data=secret)',
      },
    ])
    fixture.detectChanges()
    const el: HTMLElement = fixture.nativeElement
    const link = el.querySelector('.chat-markdown a')
    expect(link?.textContent).toBe('View original document')
    expect(link?.nextElementSibling?.textContent).toBe('(otherdomain.example)')
  })
})
