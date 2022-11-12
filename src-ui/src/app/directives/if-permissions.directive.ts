import {
  Input,
  OnInit,
  Directive,
  ViewContainerRef,
  TemplateRef,
} from '@angular/core'
import {
  PaperlessPermission,
  PermissionsService,
} from '../services/permissions.service'

@Directive({
  selector: '[ifPermissions]',
})
export class IfPermissionsDirective implements OnInit {
  // The role the user must have
  @Input()
  ifPermissions: Array<PaperlessPermission> | PaperlessPermission

  /**
   * @param {ViewContainerRef} viewContainerRef -- The location where we need to render the templateRef
   * @param {TemplateRef<any>} templateRef -- The templateRef to be potentially rendered
   * @param {PermissionsService} permissionsService -- Will give us access to the permissions a user has
   */
  constructor(
    private viewContainerRef: ViewContainerRef,
    private templateRef: TemplateRef<any>,
    private permissionsService: PermissionsService
  ) {}

  public ngOnInit(): void {
    if (
      []
        .concat(this.ifPermissions)
        .every((perm: PaperlessPermission) =>
          this.permissionsService.currentUserCan(perm)
        )
    ) {
      this.viewContainerRef.createEmbeddedView(this.templateRef)
    } else {
      this.viewContainerRef.clear()
    }
  }
}
