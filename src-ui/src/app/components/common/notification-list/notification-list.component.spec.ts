import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import {
  Notification,
  NotificationService,
} from 'src/app/services/notification.service'
import { NotificationListComponent } from './notification-list.component'

const notification = {
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

describe('NotificationListComponent', () => {
  let component: NotificationListComponent
  let fixture: ComponentFixture<NotificationListComponent>
  let notificationService: NotificationService
  let notificationSubject: Subject<Notification> = new Subject()

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NotificationListComponent,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    fixture = TestBed.createComponent(NotificationListComponent)
    notificationService = TestBed.inject(NotificationService)
    jest.replaceProperty(
      notificationService,
      'showNotification',
      notificationSubject
    )

    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should close notification', () => {
    component.notifications = [notification]
    const closenotificationSpy = jest.spyOn(
      notificationService,
      'closeNotification'
    )
    component.closeNotification()
    expect(component.notifications).toEqual([])
    expect(closenotificationSpy).toHaveBeenCalledWith(notification)
  })

  it('should unsubscribe', () => {
    const unsubscribeSpy = jest.spyOn(
      (component as any).subscription,
      'unsubscribe'
    )
    component.ngOnDestroy()
    expect(unsubscribeSpy).toHaveBeenCalled()
  })

  it('should subscribe to notificationService', () => {
    component.ngOnInit()
    notificationSubject.next(notification)
    expect(component.notifications).toEqual([notification])
  })
})
