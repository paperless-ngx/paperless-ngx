import { Injectable } from '@angular/core'
import { Subject } from 'rxjs'
import { v4 as uuidv4 } from 'uuid'

export interface Toast {
  id?: string

  content: string

  delay: number

  delayRemaining?: number

  action?: any

  actionName?: string

  classname?: string

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
      classname: 'error',
      error,
    })
  }

  showInfo(content: string, delay: number = 5000) {
    this.show({ content: content, delay: delay })
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
