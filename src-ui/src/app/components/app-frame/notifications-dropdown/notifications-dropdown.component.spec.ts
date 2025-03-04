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
import {
  Notification,
  NotificationService,
} from 'src/app/services/notification.service'
import { NotificationsDropdownComponent } from './notifications-dropdown.component'

const notifications = [
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

describe('NotificationsDropdownComponent', () => {
  let component: NotificationsDropdownComponent
  let fixture: ComponentFixture<NotificationsDropdownComponent>
  let notificationService: NotificationService
  let notificationsSubject: Subject<Notification[]> = new Subject()

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NotificationsDropdownComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(NotificationsDropdownComponent)
    notificationService = TestBed.inject(NotificationService)
    jest
      .spyOn(notificationService, 'getNotifications')
      .mockReturnValue(notificationsSubject)

    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should call getNotifications and return notifications', fakeAsync(() => {
    const spy = jest.spyOn(notificationService, 'getNotifications')

    component.ngOnInit()
    notificationsSubject.next(notifications)
    fixture.detectChanges()

    expect(spy).toHaveBeenCalled()
    expect(component.notifications).toContainEqual({
      id: 'abc-123',
      content: 'foo bar',
      delay: 5000,
    })

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should show a notification', fakeAsync(() => {
    component.ngOnInit()
    notificationsSubject.next(notifications)
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain('foo bar')

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))

  it('should toggle suppressPopupNotifications', fakeAsync((finish) => {
    component.ngOnInit()
    fixture.detectChanges()
    notificationsSubject.next(notifications)

    const spy = jest.spyOn(
      notificationService,
      'suppressPopupNotifications',
      'set'
    )
    component.onOpenChange(true)
    expect(spy).toHaveBeenCalledWith(true)

    component.ngOnDestroy()
    flush()
    discardPeriodicTasks()
  }))
})
