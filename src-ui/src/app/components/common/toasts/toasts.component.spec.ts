import {
  TestBed,
  discardPeriodicTasks,
  fakeAsync,
  flush,
} from '@angular/core/testing'
import { ToastService } from 'src/app/services/toast.service'
import { ToastsComponent } from './toasts.component'
import { ComponentFixture } from '@angular/core/testing'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { of } from 'rxjs'
import { NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { Clipboard } from '@angular/cdk/clipboard'

const toasts = [
  {
    title: 'Title',
    content: 'content',
    delay: 5000,
  },
  {
    title: 'Error 1',
    content: 'Error 1 content',
    delay: 5000,
    error: 'Error 1 string',
  },
  {
    title: 'Error 2',
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

describe('ToastsComponent', () => {
  let component: ToastsComponent
  let fixture: ComponentFixture<ToastsComponent>
  let toastService: ToastService
  let clipboard: Clipboard

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [ToastsComponent],
      imports: [HttpClientTestingModule, NgbModule],
      providers: [
        {
          provide: ToastService,
          useValue: {
            getToasts: () => of(toasts),
          },
        },
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(ToastsComponent)
    toastService = TestBed.inject(ToastService)
    clipboard = TestBed.inject(Clipboard)

    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should call getToasts and return toasts', fakeAsync(() => {
    const spy = jest.spyOn(toastService, 'getToasts')

    component.ngOnInit()
    fixture.detectChanges()

    expect(spy).toHaveBeenCalled()
    expect(component.toasts).toContainEqual({
      title: 'Title',
      content: 'content',
      delay: 5000,
    })

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show a toast', fakeAsync(() => {
    component.ngOnInit()
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain('Title')

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show an error if given with toast', fakeAsync(() => {
    component.ngOnInit()
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain('Error 1 content')

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show error details, support copy', fakeAsync(() => {
    component.ngOnInit()
    fixture.detectChanges()

    expect(fixture.nativeElement.querySelector('details')).not.toBeNull()
    expect(fixture.nativeElement.textContent).toContain(
      'Error 2 message details'
    )

    const copySpy = jest.spyOn(clipboard, 'copy')
    component.copyError(toasts[2].error)
    expect(copySpy).toHaveBeenCalled()

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should parse error text, add ellipsis', () => {
    expect(component.getErrorText(toasts[2].error)).toEqual(
      'Error 2 message details'
    )
    expect(component.getErrorText({ error: 'Error string no detail' })).toEqual(
      'Error string no detail'
    )
    expect(component.getErrorText('Error string')).toEqual('')
    expect(
      component.getErrorText({ error: new Array(205).join('a') })
    ).toContain('...')
  })
})
