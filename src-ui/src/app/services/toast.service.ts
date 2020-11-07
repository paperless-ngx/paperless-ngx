import { Injectable } from '@angular/core';
import { Subject, zip } from 'rxjs';

export interface Toast {

  title: string

  content: string

  delay?: number

  action?: any

  actionName?: string

}

@Injectable({
  providedIn: 'root'
})
export class ToastService {

  constructor() { }

  private toasts: Toast[] = []

  private toastsSubject: Subject<Toast[]> = new Subject()

  showToast(toast: Toast) {
    this.toasts.push(toast)
    this.toastsSubject.next(this.toasts)
  }

  showInfo(message: string) {
    this.showToast({title: "Information", content: message, delay: 5000})
  }

  showError(message: string) {
    this.showToast({title: "Error", content: message, delay: 10000})
  }

  closeToast(toast: Toast) {
    let index = this.toasts.findIndex(t => t == toast)
    if (index > -1) {
      this.toasts.splice(index, 1)
      this.toastsSubject.next(this.toasts)
    }
  }

  getToasts() {
    return this.toastsSubject
  }

}
