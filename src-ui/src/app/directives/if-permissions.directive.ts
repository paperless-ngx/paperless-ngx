import {
  Directive,
  inject,
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
  private viewContainerRef = inject(ViewContainerRef)
  private templateRef = inject<TemplateRef<any>>(TemplateRef)
  private permissionsService = inject(PermissionsService)

  @Input()
  pngxIfPermissions:
    | Array<{ action: PermissionAction; type: PermissionType }>
    | { action: PermissionAction; type: PermissionType }

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
