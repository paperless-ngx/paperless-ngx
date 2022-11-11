import {
  Input,
  OnInit,
  Directive,
  ViewContainerRef,
  TemplateRef,
  OnDestroy,
} from '@angular/core'
import { Subscription } from 'rxjs'
import { SettingsService } from '../services/settings.service'

@Directive({
  selector: '[ifPermissions]',
})
export class IfPermissionsDirective implements OnInit, OnDestroy {
  private subscription: Subscription[] = []
  // The role the user must have
  @Input() public ifPermissions: Array<string>

  /**
   * @param {ViewContainerRef} viewContainerRef -- The location where we need to render the templateRef
   * @param {TemplateRef<any>} templateRef -- The templateRef to be potentially rendered
   * @param {SettignsService} settignsService -- Will give us access to the permissions a user has
   */
  constructor(
    private viewContainerRef: ViewContainerRef,
    private templateRef: TemplateRef<any>,
    private settingsService: SettingsService
  ) {}

  public ngOnInit(): void {
    this.subscription.push(
      this.settingsService.permissions().subscribe((permission) => {
        if (!permission) {
          // Remove element from DOM
          this.viewContainerRef.clear()
        }
        // User permissions are checked by a permission mention in DOM
        const idx = permission.findIndex(
          (element) => this.ifPermissions.indexOf(element) !== -1
        )
        if (idx < 0) {
          this.viewContainerRef.clear()
        } else {
          // Appends the ref element to DOM
          this.viewContainerRef.createEmbeddedView(this.templateRef)
        }
      })
    )
  }

  /**
   * On destroy cancels the API if its fetching.
   */
  public ngOnDestroy(): void {
    this.subscription.forEach((subscription: Subscription) =>
      subscription.unsubscribe()
    )
  }
}
