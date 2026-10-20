import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { By } from '@angular/platform-browser'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { MAX_VISIBLE_TOASTS, ToastsComponent } from './toasts.component'

const toast = {
  content: 'Error 2 content',
  delay: 5000,
  error: {
    url: 'https://example.com',
    status: 500,
    statusText: 'Internal Server Error',
    message: 'Internal server error 500 message',
    error: { detail: 'Error 2 message details' },
  },
}

describe('ToastsComponent', () => {
  let component: ToastsComponent
  let fixture: ComponentFixture<ToastsComponent>
  let toastService: ToastService
  let toastSubject: Subject<Toast>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [ToastsComponent, NgxBootstrapIconsModule.pick(allIcons)],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    toastService = TestBed.inject(ToastService)
    toastSubject = new Subject()
    jest.replaceProperty(toastService, 'showToast', toastSubject)

    fixture = TestBed.createComponent(ToastsComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should close toast', () => {
    toastSubject.next(toast)
    const closeToastSpy = jest.spyOn(toastService, 'closeToast')
    component.closeToast(toast)
    expect(component.toasts()).toEqual([])
    expect(closeToastSpy).toHaveBeenCalledWith(toast)
  })

  it('should update from toastService', () => {
    toastSubject.next(toast)
    expect(component.toasts()).toEqual([toast])
  })

  it('should stack popups newest first, up to the maximum', () => {
    const toasts: Toast[] = Array.from(
      { length: MAX_VISIBLE_TOASTS + 1 },
      (_, i) => ({ id: `${i}`, content: `Toast ${i}`, delay: 5000 })
    )
    toasts.forEach((t) => toastSubject.next(t))
    expect(component.toasts().map((t) => t.id)).toEqual(['3', '2', '1'])

    // showing a visible toast again moves it to the top without duplicating
    toastSubject.next(toasts[1])
    expect(component.toasts().map((t) => t.id)).toEqual(['1', '3', '2'])
  })

  it('should remove a popup when it hides without closing it', () => {
    const closeToastSpy = jest.spyOn(toastService, 'closeToast')
    const first = { id: 'a', content: 'A', delay: 5000 }
    const second = { id: 'b', content: 'B', delay: 5000 }
    toastSubject.next(first)
    toastSubject.next(second)
    component.removePopup(first)
    expect(component.toasts()).toEqual([second])
    expect(closeToastSpy).not.toHaveBeenCalled()
  })

  it('should clear popups when toastService emits null', () => {
    toastSubject.next(toast)
    toastSubject.next(null)
    expect(component.toasts()).toEqual([])
  })

  it('should render one toast component per popup', () => {
    toastSubject.next({ id: 'a', content: 'A', delay: 5000 })
    toastSubject.next({ id: 'b', content: 'B', delay: 5000 })
    fixture.detectChanges()
    expect(fixture.nativeElement.querySelectorAll('pngx-toast')).toHaveLength(2)
  })

  it('should only hide the popup on close, but clear it on action', () => {
    const closeToastSpy = jest.spyOn(toastService, 'closeToast')
    const first = { id: 'a', content: 'A', delay: 5000 }
    const second = { id: 'b', content: 'B', delay: 5000 }
    toastSubject.next(first)
    toastSubject.next(second)
    fixture.detectChanges()
    const popups = fixture.debugElement.queryAll(By.css('pngx-toast'))

    popups[1].triggerEventHandler('closed', first)
    expect(closeToastSpy).not.toHaveBeenCalled()
    expect(component.toasts()).toEqual([second])

    popups[0].triggerEventHandler('actioned', second)
    expect(closeToastSpy).toHaveBeenCalledWith(second)
    expect(component.toasts()).toEqual([])
  })
})
