import { Component, OnInit } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { UserService } from 'src/app/services/rest/user.service';
import { SettingsService } from 'src/app/services/settings.service';
import { CustomField } from 'src/app/data/custom-field';
import { FormControl, FormGroup } from '@angular/forms';
import { DEFAULT_MATCHING_ALGORITHM } from 'src/app/data/matching-model';
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service';
import { Shelf } from 'src/app/data/custom-shelf';
import { CustomShelfService } from 'src/app/services/rest/custom-shelf.service';
import { CustomService } from 'src/app/services/common-service/service-shelf';
import { EditCustomShelfComponent } from '../edit-customshelf/edit-customshelf.component';

@Component({
  selector: 'pngx-custom-shelf-edit-dialog',
  templateUrl: './custom-shelf-edit-dialog.component.html',
  styleUrls: ['./custom-shelf-edit-dialog.component.scss']
})
export class CustomShelfEditDialogComponent extends EditCustomShelfComponent<Shelf> implements OnInit {
  warehouses: any[] = [];
  warehouseNames: string[] = [];
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
  //   //this.loadWarehouses();
  // }

  loadWarehouses(): void {
    this.customService.getWarehouses().subscribe(data => {
      // Lọc và chỉ lấy các warehouse có type là 'Warehouse'
      this.warehouses = data.results.filter(warehouse => warehouse.type === 'Warehouse');

      // Lấy các name của warehouse có type là 'Warehouse'
      this.warehouseNames = this.warehouses.map(warehouse => warehouse.name);
      console.log("yuguy", this.warehouses)
    });
  }



  getCreateTitle() {
    return $localize`Create new shelf`
  }

  getEditTitle() {
    return $localize`Edit shelf`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      type: new FormControl('Shelf'),
      parent_warehouse: new FormControl(''),
      matching_algorithm: new FormControl(DEFAULT_MATCHING_ALGORITHM),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
      permissions_form: new FormControl(null),
    })
  }
}
