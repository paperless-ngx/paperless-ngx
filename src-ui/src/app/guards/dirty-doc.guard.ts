import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'

export interface ComponentCanDeactivate {
  canDeactivate: () => boolean | Observable<boolean>
}

@Injectable()
export class DirtyDocGuard {
  canDeactivate(
    component: ComponentCanDeactivate
  ): boolean | Observable<boolean> {
    return component.canDeactivate()
      ? true
      : confirm(
          $localize`Warning: You have unsaved changes to your document(s).`
        )
  }
}
