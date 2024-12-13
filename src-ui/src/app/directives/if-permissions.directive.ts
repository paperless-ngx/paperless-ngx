import {
  Directive,
  Input,
  OnInit,
  TemplateRef,
  ViewContainerRef,
} from '@angular/core'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from '../services/permissions.service'

@Directive({
  selector: '[pngxIfPermissions]',
})
export class IfPermissionsDirective implements OnInit {
  @Input()
  pngxIfPermissions:
    | Array<{ action: PermissionAction; type: PermissionType }>
    | { action: PermissionAction; type: PermissionType }

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
        .concat(this.pngxIfPermissions)
        .every((perm: { action: PermissionAction; type: PermissionType }) =>
          this.permissionsService.currentUserCan(perm.action, perm.type)
        )
    ) {
      this.viewContainerRef.createEmbeddedView(this.templateRef)
    } else {
      this.viewContainerRef.clear()
    }
  }
}
