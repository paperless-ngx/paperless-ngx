import { Component } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { PaperlessCategory } from 'src/app/data/paperless-category';
import { CategoryService } from 'src/app/services/rest/category.service';
import { ToastService } from 'src/app/services/toast.service';

@Component({
  selector: 'app-category-edit-dialog',
  templateUrl: './category-edit-dialog.component.html',
  styleUrls: ['./category-edit-dialog.component.scss'],
})
export class CategoryEditDialogComponent extends EditDialogComponent<PaperlessCategory> {
  constructor(
    service: CategoryService,
    activeModal: NgbActiveModal,
    toastService: ToastService
  ) {
    super(service, activeModal, toastService);
  }

  getCreateTitle() {
    return $localize`Create new category`;
  }

  getEditTitle() {
    return $localize`Edit category`;
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      matching_algorithm: new FormControl(1),
      match: new FormControl(''),
      is_insensitive: new FormControl(true),
    });
  }
}
