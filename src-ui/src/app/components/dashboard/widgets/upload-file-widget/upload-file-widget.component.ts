import { Component, inject } from '@angular/core'
import { TourNgBootstrap } from 'ngx-ui-tour-ng-bootstrap'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { UploadDocumentsService } from 'src/app/services/upload-documents.service'
import { WidgetFrameComponent } from '../widget-frame/widget-frame.component'

@Component({
  selector: 'pngx-upload-file-widget',
  templateUrl: './upload-file-widget.component.html',
  styleUrls: ['./upload-file-widget.component.scss'],
  imports: [
    WidgetFrameComponent,
    IfPermissionsDirective,
    BootstrapIconComponent,
    TourNgBootstrap,
  ],
})
export class UploadFileWidgetComponent extends ComponentWithPermissions {
  private uploadDocumentsService = inject(UploadDocumentsService)

  public onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement
    this.uploadDocumentsService.uploadFiles(Array.from(input.files ?? []))
    input.value = ''
  }
}
