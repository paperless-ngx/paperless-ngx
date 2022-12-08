import {
  Directive,
  EmbeddedViewRef,
  Input,
  OnChanges,
  OnInit,
  TemplateRef,
  ViewContainerRef,
} from '@angular/core'
import { ObjectWithPermissions } from '../data/object-with-permissions'
import {
  PermissionAction,
  PermissionsService,
} from '../services/permissions.service'

@Directive({
  selector: '[ifObjectPermissions]',
})
export class IfObjectPermissionsDirective implements OnInit, OnChanges {
  // The role the user must have
  @Input()
  ifObjectPermissions: {
    object: ObjectWithPermissions
    action: PermissionAction
  }

  createdView: EmbeddedViewRef<any>

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
      !this.ifObjectPermissions?.object ||
      this.permissionsService.currentUserHasObjectPermissions(
        this.ifObjectPermissions.action,
        this.ifObjectPermissions.object
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
