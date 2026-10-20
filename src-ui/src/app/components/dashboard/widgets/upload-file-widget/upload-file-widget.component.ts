import { Component, inject } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { TourNgBootstrap } from 'ngx-ui-tour-ng-bootstrap'
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
    NgxBootstrapIconsModule,
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
