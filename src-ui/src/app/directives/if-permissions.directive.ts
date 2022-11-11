import {
  Input,
  OnInit,
  Directive,
  ViewContainerRef,
  TemplateRef,
} from '@angular/core'
import { SettingsService } from '../services/settings.service'

@Directive({
  selector: '[ifPermissions]',
})
export class IfPermissionsDirective implements OnInit {
  // The role the user must have
  @Input() public ifPermissions: Array<string> | string

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
    if (
      []
        .concat(this.ifPermissions)
        .every((perm) => this.settingsService.currentUserCan(perm))
    ) {
      this.viewContainerRef.createEmbeddedView(this.templateRef)
    } else {
      this.viewContainerRef.clear()
    }
  }
}
