import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ElementRef } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NavigationEnd, Router } from '@angular/router'
import { allIcons, NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import { ChatService } from 'src/app/services/chat.service'
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
      imports: [NgxBootstrapIconsModule.pick(allIcons), ChatComponent],
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
    expect(component.documentId).toBe(123)
  })

  it('should update documentId on navigation', () => {
    component.ngOnInit()
    routerEvents$.next(new NavigationEnd(1, '/documents/456', '/documents/456'))
    expect(component.documentId).toBe(456)
  })

  it('should return correct placeholder based on documentId', () => {
    component.documentId = 123
    expect(component.placeholder).toBe('Ask a question about this document...')
    component.documentId = undefined
    expect(component.placeholder).toBe('Ask a question about a document...')
  })

  it('should send a message and handle streaming response', () => {
    component.input = 'Hello'
    component.sendMessage()

    expect(component.messages.length).toBe(2)
    expect(component.messages[0].content).toBe('Hello')
    expect(component.loading).toBe(true)

    mockStream$.next('Hi')
    expect(component.messages[1].content).toBe('H')
    mockStream$.next('Hi there')
    // advance time to process the typewriter effect
    jest.advanceTimersByTime(1000)
    expect(component.messages[1].content).toBe('Hi there')

    mockStream$.complete()
    expect(component.loading).toBe(false)
    expect(component.messages[1].isStreaming).toBe(false)
  })

  it('should handle errors during streaming', () => {
    component.input = 'Hello'
    component.sendMessage()

    mockStream$.error('Error')
    expect(component.messages[1].content).toContain(
      '⚠️ Error receiving response.'
    )
    expect(component.loading).toBe(false)
  })

  it('should enqueue typewriter chunks correctly', () => {
    const message = { content: '', role: 'assistant', isStreaming: true }
    component.enqueueTypewriter(null, message as any) // coverage for null
    component.enqueueTypewriter('Hello', message as any)
    expect(component['typewriterBuffer'].length).toBe(4)
  })

  it('should scroll to bottom after sending a message', () => {
    const scrollSpy = jest.spyOn(
      ChatComponent.prototype as any,
      'scrollToBottom'
    )
    component.input = 'Test'
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
})
