import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

export class Toast {

  static make(title: string, content: string, delay?: number): Toast {
    let t = new Toast()
    t.title = title
    t.content = content
    if (delay) {
      t.delay = delay
    }
    return t
  }

  title: string

  content: string

  delay: number = 5000

}

@Injectable({
  providedIn: 'root'
})
export class ToastService {

  constructor() { }

  private toasts: Toast[] = []

  private toastSubject: Subject<Toast[]> = new Subject()

  showToast(toast: Toast) {
    this.toasts.push(toast)
    this.toastSubject.next(this.toasts)
  }

  closeToast(toast: Toast) {
    let index = this.toasts.findIndex(t => t == toast)
    if (index > -1) {
      this.toasts.splice(index, 1)
      this.toastSubject.next(this.toasts)
    }
  }

  getToasts() {
    return this.toastSubject
  }

}
