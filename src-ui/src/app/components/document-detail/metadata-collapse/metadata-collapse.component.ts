import { Component, Input } from '@angular/core'

@Component({
  selector: 'app-metadata-collapse',
  templateUrl: './metadata-collapse.component.html',
  styleUrls: ['./metadata-collapse.component.scss'],
})
export class MetadataCollapseComponent {
  constructor() {}

  expand = false

  @Input()
  metadata

  @Input()
  title = $localize`Metadata`
}
