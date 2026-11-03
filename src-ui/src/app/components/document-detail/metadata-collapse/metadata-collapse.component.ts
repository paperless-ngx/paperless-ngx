import { Component, Input } from '@angular/core'
import { NgbCollapseModule } from '@ng-bootstrap/ng-bootstrap'
import { BootstrapIconComponent } from 'src/app/components/common/bootstrap-icon/bootstrap-icon.component'

@Component({
  selector: 'pngx-metadata-collapse',
  templateUrl: './metadata-collapse.component.html',
  styleUrls: ['./metadata-collapse.component.scss'],
  imports: [NgbCollapseModule, BootstrapIconComponent],
})
export class MetadataCollapseComponent {
  constructor() {}

  expand = false

  @Input()
  metadata

  @Input()
  title = $localize`Metadata`
}
