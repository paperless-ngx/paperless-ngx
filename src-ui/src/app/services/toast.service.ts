import { Injectable } from '@angular/core';
import { Subject, zip } from 'rxjs';

export class Toast {

  static make(title: string, content: string, classname?: string, delay?: number): Toast {
    let t = new Toast()
    t.title = title
    t.content = content
    t.classname = classname
    if (delay) {
      t.delay = delay
    }
    return t
  }

  static makeError(content: string) {
    return Toast.make("Error", content, null, 10000)
  }

  title: string

  classname: string

  content: string

  delay: number = 5000

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
