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
import { PermissionsService } from '../services/permissions.service'

@Directive({
  selector: '[pngxIfOwner]',
})
export class IfOwnerDirective implements OnInit, OnChanges {
  private viewContainerRef = inject(ViewContainerRef)
  private templateRef = inject<TemplateRef<any>>(TemplateRef)
  private permissionsService = inject(PermissionsService)

  // The role the user must have
  @Input()
  pngxIfOwner: ObjectWithPermissions

  createdView: EmbeddedViewRef<any>

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
