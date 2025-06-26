import {
  Directive,
  EmbeddedViewRef,
  Input,
  OnChanges,
  OnInit,
  TemplateRef,
  ViewContainerRef,
  inject,
} from '@angular/core'
import { ObjectWithPermissions } from '../data/object-with-permissions'
import {
  PermissionAction,
  PermissionsService,
} from '../services/permissions.service'

@Directive({
  selector: '[pngxIfObjectPermissions]',
})
export class IfObjectPermissionsDirective implements OnInit, OnChanges {
  private viewContainerRef = inject(ViewContainerRef)
  private templateRef = inject<TemplateRef<any>>(TemplateRef)
  private permissionsService = inject(PermissionsService)

  // The role the user must have
  @Input()
  pngxIfObjectPermissions: {
    object: ObjectWithPermissions
    action: PermissionAction
  }

  createdView: EmbeddedViewRef<any>

  public ngOnInit(): void {
    if (
      !this.pngxIfObjectPermissions?.object ||
      this.permissionsService.currentUserHasObjectPermissions(
        this.pngxIfObjectPermissions.action,
        this.pngxIfObjectPermissions.object
      )
    ) {
      if (!this.createdView)
        this.createdView = this.viewContainerRef.createEmbeddedView(
          this.templateRef
        )
    } else {
      this.viewContainerRef.clear()
    }
  }

  public ngOnChanges(): void {
    this.ngOnInit()
  }
}
