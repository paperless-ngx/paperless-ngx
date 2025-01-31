import { Component } from '@angular/core'
import { RouterModule } from '@angular/router'
import { TourNgBootstrapModule } from 'ngx-ui-tour-ng-bootstrap'
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
    RouterModule,
    TourNgBootstrapModule,
  ],
})
export class UploadFileWidgetComponent extends ComponentWithPermissions {
  constructor(private uploadDocumentsService: UploadDocumentsService) {
    super()
  }

  public onFileSelected(event: Event) {
    this.uploadDocumentsService.uploadFiles(
      (event.target as HTMLInputElement).files
    )
  }
}
