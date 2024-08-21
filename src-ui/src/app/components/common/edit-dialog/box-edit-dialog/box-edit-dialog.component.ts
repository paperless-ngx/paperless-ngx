import { Component, OnInit } from '@angular/core';
import { Box } from 'src/app/data/box';
import { EditDialogComponent } from '../edit-dialog.component';
import { UserService } from 'src/app/services/rest/user.service';
import { SettingsService } from 'src/app/services/settings.service';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { FormControl, FormGroup } from '@angular/forms';
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model';
import { BoxService } from 'src/app/services/rest/box.service';
import { CustomService } from 'src/app/services/common-service/service-shelf';

import { Shelf } from 'src/app/data/custom-shelf';
import { CustomShelfService } from 'src/app/services/rest/custom-shelf.service';
import { EditCustomBoxComponent } from '../edit-custombox/edit-custombox.component';

@Component({
  selector: 'pngx-box-edit-dialog',
  templateUrl: './box-edit-dialog.component.html',
  styleUrls: ['./box-edit-dialog.component.scss']
})
export class BoxEditDialogComponent extends EditCustomBoxComponent<Shelf> implements OnInit {
  warehouses: any[] = [];
  warehouseNames: string[] = [];
  shelfs: any[] = [];
  constructor(
    service: CustomShelfService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService,
    private customService: CustomService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  // ngOnInit(): void {
  //   this.loadShelf();
  //   console.log("fddd", this.object)
  //   this.objectForm.get('name').setValue(this.object?.name ?? '');
  // }


  loadShelf(): void {
    this.customService.getShelf().subscribe(data => {
      this.warehouses = data.results.filter(warehouse => warehouse.type === 'Warehouse');
      this.shelfs = data.results.filter(warehouse => warehouse.type === 'Shelf');
    });
  }

  loadShelvesByWarehouseId(warehouseId: any): void {

    this.customService.getShelfId(warehouseId).subscribe(data => {
      // this.shelfs = data.results;
      this.shelfs = data.results.filter(warehouse => warehouse.type === 'Shelf',);
      if (this.shelfs.length > 0) {
        this.objectForm.get('parent_warehouse')?.setValue(this.shelfs[0].id);
      }
    });
  }

  onWarehouseChange(event: Event): void {
    const warehouseId = (event.target as HTMLSelectElement).value;
    // console.log("dd", warehouseId)
    this.loadShelvesByWarehouseId(warehouseId);
  }

  onShelfChange(event: Event): void {
    // Handle shelf change logic here if needed
  }


  getCreateTitle() {
    return $localize`Create new Boxcase`
  }

  getEditTitle() {
    return $localize`Edit Boxcase`
  }

  getForm(): FormGroup {
    return new FormGroup({
      //name: new FormControl(this.object?.name ?? ''),
      name: new FormControl(''),
      type: new FormControl('Boxcase'),
      parent_warehouse: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}