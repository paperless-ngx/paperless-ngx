import { Injectable } from '@angular/core'
import { Subject } from 'rxjs'

export interface Toast {
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

  private toasts: Toast[] = []

  private toastsSubject: Subject<Toast[]> = new Subject()

  show(toast: Toast) {
    this.toasts.push(toast)
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
    let index = this.toasts.findIndex((t) => t == toast)
    if (index > -1) {
      this.toasts.splice(index, 1)
      this.toastsSubject.next(this.toasts)
    }
  }

  getToasts() {
    return this.toastsSubject
  }
}
