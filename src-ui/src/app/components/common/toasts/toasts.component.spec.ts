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

describe('ToastsComponent', () => {
  let component: ToastsComponent
  let fixture: ComponentFixture<ToastsComponent>
  let toastService: ToastService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [ToastsComponent],
      imports: [HttpClientTestingModule, NgbModule],
      providers: [
        {
          provide: ToastService,
          useValue: {
            getToasts: () =>
              of([
                {
                  title: 'Title',
                  content: 'content',
                  delay: 5000,
                },
                {
                  title: 'Error',
                  content: 'Error content',
                  delay: 5000,
                  error: new Error('Error message'),
                },
              ]),
          },
        },
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(ToastsComponent)
    component = fixture.componentInstance

    toastService = TestBed.inject(ToastService)

    fixture.detectChanges()
  })

  it('should call getToasts and return toasts', fakeAsync(() => {
    const spy = jest.spyOn(toastService, 'getToasts').mockReset()

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
    expect(fixture.nativeElement.textContent).toContain('Error message')

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))
})
