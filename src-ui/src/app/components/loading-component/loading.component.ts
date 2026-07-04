import { Directive, OnDestroy, signal } from '@angular/core'
import { Subject } from 'rxjs'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'

@Directive()
export abstract class LoadingComponentWithPermissions
  extends ComponentWithPermissions
  implements OnDestroy
{
  private loadingSignal = signal(true)
  private showSignal = signal(false)

  public get loading(): boolean {
    return this.loadingSignal()
  }

  public set loading(value: boolean) {
    this.loadingSignal.set(value)
  }

  public get show(): boolean {
    return this.showSignal()
  }

  public set show(value: boolean) {
    this.showSignal.set(value)
  }

  protected unsubscribeNotifier: Subject<any> = new Subject()

  constructor() {
    super()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }
}
