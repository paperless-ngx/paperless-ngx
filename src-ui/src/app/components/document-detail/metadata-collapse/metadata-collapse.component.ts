import { Component, Input, OnInit } from '@angular/core';

@Component({
  selector: 'app-metadata-collapse',
  templateUrl: './metadata-collapse.component.html',
  styleUrls: ['./metadata-collapse.component.scss']
})
export class MetadataCollapseComponent implements OnInit {

  constructor() { }

  expand = false

  @Input()
  metadata

  @Input()
  title = $localize`Metadata`

  ngOnInit(): void {
  }

}
