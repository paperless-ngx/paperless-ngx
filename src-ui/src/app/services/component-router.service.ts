import { Injectable, inject } from '@angular/core'
import { ActivationStart, Event, Router } from '@angular/router'
import { filter } from 'rxjs'

const EXCLUDE_COMPONENTS = ['AppFrameComponent']

@Injectable({
  providedIn: 'root',
})
export class ComponentRouterService {
  private router = inject(Router)

  private history: string[] = []
  private componentHistory: any[] = []

  constructor() {
    this.router.events
      .pipe(filter((event: Event) => event instanceof ActivationStart))
      .subscribe((event: ActivationStart) => {
        const url = this.getSnapshotUrl(event)
        if (
          this.componentHistory[this.componentHistory.length - 1] !==
            event.snapshot.data.componentName &&
          !EXCLUDE_COMPONENTS.includes(event.snapshot.data.componentName)
        ) {
          this.history.push(url)
          this.componentHistory.push(event.snapshot.data.componentName)
        } else {
          // Update the URL of the current component in case the same component was loaded via a different URL
          this.history[this.history.length - 1] = url
        }
      })
  }

  private getSnapshotUrl(event: ActivationStart): string {
    const url: unknown = event.snapshot.url
    if (Array.isArray(url)) {
      return url.map((segment) => segment.path ?? segment.toString()).join('/')
    }
    return url?.toString() ?? ''
  }

  public getComponentURLBefore(): any {
    if (this.componentHistory.length > 1) {
      return this.history[this.history.length - 2]
    }
    return null
  }
}
