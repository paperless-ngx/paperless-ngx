import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import { Toast, ToastService } from 'src/app/services/toast.service'
import { ToastsComponent } from './toasts.component'

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
    component.closeToast()
    expect(component.toasts()).toEqual([])
    expect(closeToastSpy).toHaveBeenCalledWith(toast)
  })

  it('should update from toastService', () => {
    toastSubject.next(toast)
    expect(component.toasts()).toEqual([toast])
  })
})
