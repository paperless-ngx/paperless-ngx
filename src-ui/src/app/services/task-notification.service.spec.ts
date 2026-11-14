import { TestBed } from '@angular/core/testing'
import { Router } from '@angular/router'
import { BulkOperationStatus } from '../data/bulk-operation'
import { PaperlessTaskStatus } from '../data/paperless-task'
import { PermissionsService } from './permissions.service'
import { TaskNotificationService } from './task-notification.service'
import { Toast, ToastLevel, ToastService } from './toast.service'

describe('TaskNotificationService', () => {
  let service: TaskNotificationService
  let toastService: ToastService
  let popups: Toast[]
  let notifications: Toast[]
  const navigate = jest.fn()
  const currentUserCan = jest.fn()
  const result = (
    status = PaperlessTaskStatus.Success
  ): BulkOperationStatus => ({
    task_id: 'task-1',
    operation: 'run_workflow',
    status,
  })

  beforeEach(() => {
    jest.useFakeTimers()
    currentUserCan.mockReturnValue(true)
    TestBed.configureTestingModule({
      providers: [
        { provide: Router, useValue: { navigate } },
        { provide: PermissionsService, useValue: { currentUserCan } },
      ],
    })
    service = TestBed.inject(TaskNotificationService)
    toastService = TestBed.inject(ToastService)
    popups = []
    notifications = []
    toastService.showToast.subscribe((toast) => popups.push(toast))
    toastService
      .getToasts()
      .subscribe((toasts) => (notifications = [...toasts]))
  })

  afterEach(() => {
    jest.clearAllTimers()
    jest.useRealTimers()
  })

  it('replaces a queued notification with its result, removing the task link on success', () => {
    service.showQueued('task-1', 'Workflow queued.', {
      content: 'Workflow completed.',
    })
    jest.advanceTimersByTime(399)
    expect(popups).toHaveLength(0)
    jest.advanceTimersByTime(1)
    expect(popups[0].content).toBe('Workflow queued.')
    expect(popups[0].actionName).toBe('View task')
    popups[0].action()
    expect(navigate).toHaveBeenCalledWith(['/tasks'], {
      queryParams: { task_id: 'task-1' },
    })
    service.complete(result())
    expect(notifications).toHaveLength(1)
    expect(popups[1]).toEqual(
      expect.objectContaining({
        id: popups[0].id,
        content: 'Workflow completed.',
        level: ToastLevel.Success,
      })
    )
    expect(popups[1].action).toBeUndefined()
    expect(popups[1].actionName).toBeUndefined()
  })

  it('shows only the result when a task completes during the grace period', () => {
    service.showQueued('task-1', 'Queued')
    jest.advanceTimersByTime(100)
    service.complete(result())
    jest.advanceTimersByTime(1000)
    expect(popups.map((toast) => toast.content)).toEqual([
      'Operation completed.',
    ])
  })

  it('does not show a stale queued state when completion beats the HTTP response', () => {
    service.complete(result())
    service.showQueued('task-1', 'Workflow queued.', {
      content: 'Workflow completed.',
    })
    jest.advanceTimersByTime(1000)
    expect(popups.every((toast) => toast.level === ToastLevel.Success)).toBe(
      true
    )
    expect(notifications).toHaveLength(1)
    expect(notifications[0].content).toBe('Workflow completed.')
    expect(notifications[0].action).toBeUndefined()
  })

  it.each([PaperlessTaskStatus.Failure, PaperlessTaskStatus.Revoked])(
    'replaces the queued state with an error for %s',
    (status) => {
      service.showQueued('task-1', 'Queued', {
        content: 'Success',
        actionName: 'Undo',
      })
      jest.advanceTimersByTime(400)
      service.complete({ ...result(status), error: 'Task failed' })
      expect(notifications).toHaveLength(1)
      expect(notifications[0]).toEqual(
        expect.objectContaining({
          level: ToastLevel.Error,
          error: 'Task failed',
          actionName: 'View task',
        })
      )
    }
  )

  it('ignores nonterminal and duplicate outcomes', () => {
    service.showQueued('task-1', 'Queued')
    service.complete(result(PaperlessTaskStatus.Started))
    expect(popups).toHaveLength(0)
    service.complete(result())
    service.complete(result())
    expect(popups).toHaveLength(1)
  })

  it('keeps concurrent task notifications separate', () => {
    service.showQueued('task-1', 'First queued')
    service.showQueued('task-2', 'Second queued')
    jest.advanceTimersByTime(400)
    service.complete(result())
    expect(notifications).toHaveLength(2)
    expect(notifications.map((toast) => toast.content)).toEqual([
      'Second queued',
      'Operation completed.',
    ])
  })

  it('omits task links without task viewing permission', () => {
    currentUserCan.mockReturnValue(false)
    service.showQueued('task-1', 'Queued')
    jest.advanceTimersByTime(400)
    service.complete(result())
    expect(popups.every((toast) => !toast.action && !toast.actionName)).toBe(
      true
    )
  })
})
