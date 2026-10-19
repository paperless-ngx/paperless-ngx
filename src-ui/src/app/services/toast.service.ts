import { Injectable } from '@angular/core'
import { Subject } from 'rxjs'
import { v4 as uuidv4 } from 'uuid'

export enum ToastLevel {
  Info = 'info',
  Success = 'success',
  Error = 'error',
}

export interface Toast {
  id?: string

  content: string

  delay: number

  action?: any

  actionName?: string

  /** Defaults to ToastLevel.Info */
  level?: ToastLevel

  error?: any
}

@Injectable({
  providedIn: 'root',
})
export class ToastService {
  constructor() {}
  _suppressPopupToasts: boolean

  set suppressPopupToasts(value: boolean) {
    this._suppressPopupToasts = value
    this.showToast.next(null)
  }

  private toasts: Toast[] = []

  private toastsSubject: Subject<Toast[]> = new Subject()

  public showToast: Subject<Toast> = new Subject()

  show(toast: Toast) {
    if (!toast.id) {
      toast.id = uuidv4()
    }
    if (typeof toast.error === 'string') {
      try {
        toast.error = JSON.parse(toast.error)
      } catch (e) {}
    }
    this.toasts.unshift(toast)
    if (!this._suppressPopupToasts) {
      this.showToast.next(toast)
    }
    this.toastsSubject.next(this.toasts)
  }

  showError(content: string, error: any = null, delay: number = 10000) {
    this.show({
      content: content,
      delay: delay,
      level: ToastLevel.Error,
      error,
    })
  }

  showInfo(content: string, delay: number = 5000) {
    this.show({ content: content, delay: delay })
  }

  /** For confirming that something the user did has completed */
  showSuccess(content: string, delay: number = 5000) {
    this.show({ content: content, delay: delay, level: ToastLevel.Success })
  }

  closeToast(toast: Toast) {
    let index = this.toasts.findIndex((t) => t.id == toast.id)
    if (index > -1) {
      this.toasts.splice(index, 1)
      this.toastsSubject.next(this.toasts)
    }
  }

  getToasts() {
    return this.toastsSubject
  }

  clearToasts() {
    this.toasts = []
    this.toastsSubject.next(this.toasts)
    this.showToast.next(null)
  }
}
