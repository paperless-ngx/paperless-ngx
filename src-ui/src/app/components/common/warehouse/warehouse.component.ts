import { Component, Input } from '@angular/core'
import { Warehouse } from 'src/app/data/warehouse'

@Component({
  selector: 'pngx-warehouse',
  templateUrl: './warehouse.component.html',
  styleUrls: ['./warehouse.component.scss'],
})
export class WarehouseComponent {
  constructor() {}

  @Input()
  warehouse: Warehouse

  @Input()
  linkTitle: string = ''

  @Input()
  clickable: boolean = false
}
