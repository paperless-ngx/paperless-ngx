import { TestBed } from '@angular/core/testing'
import { NotificationService } from './notification.service'

describe('NotificationService', () => {
  let notificationService: NotificationService

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [NotificationService],
    })

    notificationService = TestBed.inject(NotificationService)
  })

  it('adds notification on show', () => {
    const notification = {
      title: 'Title',
      content: 'content',
      delay: 5000,
    }
    notificationService.show(notification)

    notificationService.getNotifications().subscribe((notifications) => {
      expect(notifications).toContainEqual(notification)
    })
  })

  it('adds a unique id to notification on show', () => {
    const notification = {
      title: 'Title',
      content: 'content',
      delay: 5000,
    }
    notificationService.show(notification)

    notificationService.getNotifications().subscribe((notifications) => {
      expect(notifications[0].id).toBeDefined()
    })
  })

  it('parses error string to object on show', () => {
    const notification = {
      title: 'Title',
      content: 'content',
      delay: 5000,
      error: 'Error string',
    }
    notificationService.show(notification)

    notificationService.getNotifications().subscribe((notifications) => {
      expect(notifications[0].error).toEqual('Error string')
    })
  })

  it('creates notifications with defaults on showInfo and showError', () => {
    notificationService.showInfo('Info notification')
    notificationService.showError('Error notification')

    notificationService.getNotifications().subscribe((notifications) => {
      expect(notifications).toContainEqual({
        content: 'Info notification',
        delay: 5000,
      })
      expect(notifications).toContainEqual({
        content: 'Error notification',
        delay: 10000,
      })
    })
  })

  it('removes notification on close', () => {
    const notification = {
      title: 'Title',
      content: 'content',
      delay: 5000,
    }
    notificationService.show(notification)
    notificationService.closeNotification(notification)

    notificationService.getNotifications().subscribe((notifications) => {
      expect(notifications).toHaveLength(0)
    })
  })

  it('clears all notifications on clear', () => {
    notificationService.showInfo('Info notification')
    notificationService.showError('Error notification')
    notificationService.clearNotifications()

    notificationService.getNotifications().subscribe((notifications) => {
      expect(notifications).toHaveLength(0)
    })
  })

  it('suppresses popup notifications if suppressPopupNotifications is true', (finish) => {
    notificationService.showNotification.subscribe((notification) => {
      expect(notification).not.toBeNull()
    })
    notificationService.showInfo('Info notification')

    notificationService.showNotification.subscribe((notification) => {
      expect(notification).toBeNull()
      finish()
    })

    notificationService.suppressPopupNotifications = true
    notificationService.showInfo('Info notification')
  })
})
