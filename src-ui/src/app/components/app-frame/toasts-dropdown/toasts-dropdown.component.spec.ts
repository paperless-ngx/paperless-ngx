import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import {
  ComponentFixture,
  TestBed,
  discardPeriodicTasks,
  fakeAsync,
  flush,
} from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import { Toast, ToastService } from 'src/app/services/toast.service'
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
  let toastsSubject: Subject<Toast[]> = new Subject()

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

    fixture = TestBed.createComponent(ToastsDropdownComponent)
    toastService = TestBed.inject(ToastService)
    jest.spyOn(toastService, 'getToasts').mockReturnValue(toastsSubject)

    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should call getToasts and return toasts', fakeAsync(() => {
    const spy = jest.spyOn(toastService, 'getToasts')

    component.ngOnInit()
    toastsSubject.next(toasts)
    fixture.detectChanges()

    expect(spy).toHaveBeenCalled()
    expect(component.toasts).toContainEqual({
      id: 'abc-123',
      content: 'foo bar',
      delay: 5000,
    })

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show a toast', fakeAsync(() => {
    component.ngOnInit()
    toastsSubject.next(toasts)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain('foo bar')

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should toggle suppressPopupToasts', fakeAsync((finish) => {
    component.ngOnInit()
    fixture.detectChanges()
    toastsSubject.next(toasts)

    const spy = jest.spyOn(toastService, 'suppressPopupToasts', 'set')
    component.onOpenChange(true)
    expect(spy).toHaveBeenCalledWith(true)

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))
})
