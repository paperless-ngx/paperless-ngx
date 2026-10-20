import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import { Toast, ToastLevel, ToastService } from 'src/app/services/toast.service'
import { ToastsDropdownComponent } from './toasts-dropdown.component'

const toasts = [
  {
    id: 'abc-123',
    content: 'foo bar',
    delay: 5000,
  },
  {
    id: 'def-123',
    content: 'Error 1 content',
    delay: 5000,
    error: 'Error 1 string',
  },
  {
    id: 'ghi-123',
    content: 'Error 2 content',
    delay: 5000,
    error: {
      url: 'https://example.com',
      status: 500,
      statusText: 'Internal Server Error',
      message: 'Internal server error 500 message',
      error: { detail: 'Error 2 message details' },
    },
  },
]

describe('ToastsDropdownComponent', () => {
  let component: ToastsDropdownComponent
  let fixture: ComponentFixture<ToastsDropdownComponent>
  let toastService: ToastService
  let toastsSubject: Subject<Toast[]>
  let getToastsSpy: jest.SpyInstance

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        ToastsDropdownComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    toastService = TestBed.inject(ToastService)
    toastsSubject = new Subject()
    getToastsSpy = jest
      .spyOn(toastService, 'getToasts')
      .mockReturnValue(toastsSubject)

    fixture = TestBed.createComponent(ToastsDropdownComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should call getToasts and return toasts', () => {
    toastsSubject.next(toasts)
    fixture.detectChanges()

    expect(getToastsSpy).toHaveBeenCalled()
    expect(component.toasts()).toContainEqual({
      id: 'abc-123',
      content: 'foo bar',
      delay: 5000,
    })
  })

  it('should show a toast', () => {
    toastsSubject.next(toasts)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain('foo bar')
  })

  it('should toggle suppressPopupToasts', () => {
    fixture.detectChanges()
    toastsSubject.next(toasts)

    const spy = jest.spyOn(toastService, 'suppressPopupToasts', 'set')
    component.onOpenChange(true)
    expect(spy).toHaveBeenCalledWith(true)
  })

  it('should badge unread toasts, red when one is an error', () => {
    toastsSubject.next([
      { id: 'a', content: 'Read', delay: 5000, read: true },
      { id: 'b', content: 'Unread', delay: 5000, read: false },
    ])
    fixture.detectChanges()
    let badge: HTMLElement = fixture.nativeElement.querySelector(
      '.notification-count'
    )
    expect(badge.textContent.trim()).toEqual('1')
    expect(badge.classList).toContain('bg-secondary')

    toastsSubject.next([
      { id: 'c', content: 'Failed', delay: 5000, level: ToastLevel.Error },
    ])
    fixture.detectChanges()
    badge = fixture.nativeElement.querySelector('.notification-count')
    expect(badge.classList).toContain('bg-danger')

    toastsSubject.next([{ id: 'd', content: 'Seen', delay: 5000, read: true }])
    fixture.detectChanges()
    expect(
      fixture.nativeElement.querySelector('.notification-count')
    ).toBeNull()
  })

  it('should mark all toasts read when opened', () => {
    const markSpy = jest.spyOn(toastService, 'markAllRead')
    component.onOpenChange(false)
    expect(markSpy).not.toHaveBeenCalled()
    component.onOpenChange(true)
    expect(markSpy).toHaveBeenCalled()
  })
})
