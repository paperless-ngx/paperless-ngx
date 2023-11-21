import { Component, OnInit } from '@angular/core'
import { FormControl, FormGroup } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { ProfileService } from 'src/app/services/profile.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-profile-edit-dialog',
  templateUrl: './profile-edit-dialog.component.html',
  styleUrls: ['./profile-edit-dialog.component.scss'],
})
export class ProfileEditDialogComponent implements OnInit {
  public networkActive: boolean = false
  public error: any

  public form = new FormGroup({
    email: new FormControl(''),
    password: new FormControl(null),
    first_name: new FormControl(''),
    last_name: new FormControl(''),
  })

  constructor(
    private profileService: ProfileService,
    public activeModal: NgbActiveModal,
    private toastService: ToastService
  ) {}

  ngOnInit(): void {
    this.profileService.get().subscribe((profile) => {
      this.form.patchValue(profile)
    })
  }

  save() {
    const profile = Object.assign({}, this.form.value)
    this.profileService.update(profile).subscribe({
      next: () => {
        this.toastService.showInfo($localize`Profile updated successfully`)
        this.activeModal.close()
      },
      error: (error) => {
        this.toastService.showError($localize`Error saving profile`, error)
      },
    })
  }

  cancel() {
    this.activeModal.close()
  }
}
