import { Injectable } from '@angular/core';
import { Subject, zip } from 'rxjs';

export interface Toast {

  title: string

  content: string

  delay: number

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

  show(toast: Toast) {
    this.toasts.push(toast)
    this.toastsSubject.next(this.toasts)
  }

  showError(content: string, delay: number = 10000) {
    this.show({title: $localize`Error`, content: content, delay: delay})
  }

  showInfo(content: string, delay: number = 5000) {
    this.show({title: $localize`Information`, content: content, delay: delay})
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
