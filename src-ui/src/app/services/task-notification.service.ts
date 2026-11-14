import { inject, Injectable, OnDestroy } from '@angular/core'
import { Router } from '@angular/router'
import { BulkOperationStatus } from '../data/bulk-operation'
import { PaperlessTaskStatus } from '../data/paperless-task'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from './permissions.service'
import { Toast, ToastLevel, ToastService } from './toast.service'

interface PendingNotification {
  success: Partial<Toast>
  timer: ReturnType<typeof setTimeout>
}

@Injectable({ providedIn: 'root' })
export class TaskNotificationService implements OnDestroy {
  private toastService = inject(ToastService)
  private router = inject(Router)
  private permissionsService = inject(PermissionsService)
  private pending = new Map<string, PendingNotification>()
  private completed = new Map<string, BulkOperationStatus>()

  ngOnDestroy() {
    this.pending.forEach(({ timer }) => clearTimeout(timer))
  }

  showQueued(taskId: string, content: string, success: Partial<Toast> = {}) {
    const completed = this.completed.get(taskId)
    if (completed) {
      this.showResult(completed, success)
      return
    }
    if (this.pending.has(taskId)) return
    this.pending.set(taskId, {
      success,
      // short delay in case the task finishes super fast
      timer: setTimeout(() => this.show(taskId, { content, delay: 5000 }), 400),
    })
  }

  complete(result: BulkOperationStatus) {
    if (
      ![
        PaperlessTaskStatus.Success,
        PaperlessTaskStatus.Failure,
        PaperlessTaskStatus.Revoked,
      ].includes(result.status) ||
      this.completed.has(result.task_id)
    )
      return

    this.completed.set(result.task_id, result)
    // Retain recent outcomes in case task finishes quickly
    if (this.completed.size > 100) {
      this.completed.delete(this.completed.keys().next().value)
    }
    const pending = this.pending.get(result.task_id)
    if (pending) {
      clearTimeout(pending.timer)
      this.pending.delete(result.task_id)
    }
    // Trash needs the caller's document IDs to offer Undo on success.
    if (
      pending ||
      result.operation !== 'delete' ||
      result.status !== PaperlessTaskStatus.Success
    ) {
      this.showResult(result, pending?.success)
    }
  }

  private showResult(
    result: BulkOperationStatus,
    success: Partial<Toast> = {}
  ) {
    const succeeded = result.status === PaperlessTaskStatus.Success
    this.show(result.task_id, {
      content: succeeded
        ? $localize`Operation completed.`
        : result.status === PaperlessTaskStatus.Revoked
          ? $localize`Operation revoked.`
          : $localize`Operation failed. Some changes may already have been applied.`,
      delay: succeeded ? 5000 : 10000,
      level: succeeded ? ToastLevel.Success : ToastLevel.Error,
      ...(succeeded ? success : { error: result.error }),
    })
  }

  private show(taskId: string, toast: Toast) {
    const canViewTasks = this.permissionsService.currentUserCan(
      PermissionAction.View,
      PermissionType.PaperlessTask
    )
    this.toastService.show({
      id: `task-${taskId}`,
      ...(canViewTasks
        ? {
            actionName: $localize`View task`,
            action: () =>
              this.router.navigate(['/tasks'], {
                queryParams: { task_id: taskId },
              }),
          }
        : {}),
      ...toast,
    })
  }
}
