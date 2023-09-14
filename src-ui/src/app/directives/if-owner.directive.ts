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
import { PermissionsService } from '../services/permissions.service'

@Directive({
  selector: '[pngxIfOwner]',
})
export class IfOwnerDirective implements OnInit, OnChanges {
  // The role the user must have
  @Input()
  pngxIfOwner: ObjectWithPermissions

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
    if (this.permissionsService.currentUserOwnsObject(this.pngxIfOwner)) {
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
