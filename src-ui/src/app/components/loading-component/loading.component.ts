import { Subject } from 'rxjs'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { Directive, OnDestroy } from '@angular/core'

@Directive()
export abstract class LoadingComponentWithPermissions
  extends ComponentWithPermissions
  implements OnDestroy
{
  public loading: boolean = true
  public reveal: boolean = false

  protected unsubscribeNotifier: Subject<any> = new Subject()

  constructor() {
    super()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }
}
