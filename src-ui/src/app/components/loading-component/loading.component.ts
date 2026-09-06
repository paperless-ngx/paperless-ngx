import { Directive, OnDestroy, signal } from '@angular/core'
import { Subject } from 'rxjs'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'

@Directive()
export abstract class LoadingComponentWithPermissions
  extends ComponentWithPermissions
  implements OnDestroy
{
  readonly loading = signal(true)
  readonly show = signal(false)

  protected unsubscribeNotifier: Subject<any> = new Subject()

  constructor() {
    super()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }
}
