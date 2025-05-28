import { CommonModule } from '@angular/common'
import { Component } from '@angular/core'
import { MessageService } from 'primeng/api'
import { ButtonModule } from 'primeng/button'
import { FileUploadModule } from 'primeng/fileupload'
import { ToastModule } from 'primeng/toast'

@Component({
    selector: 'app-file-demo',
    standalone: true,
    imports: [CommonModule, FileUploadModule, ToastModule, ButtonModule],
    template: `<p-toast />
        <div class="grid grid-cols-12 gap-8">
            <div class="col-span-full lg:col-span-6">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Advanced</div>
                    <p-fileupload name="demo[]" (onUpload)="onUpload($event)" [multiple]="true" accept="image/*" maxFileSize="1000000" mode="advanced" url="https://www.primefaces.org/cdn/api/upload.php">
                        <ng-template #empty>
                            <div>Drag and drop files to here to upload.</div>
                        </ng-template>
                        <ng-template #content>
                            <ul *ngIf="uploadedFiles.length">
                                <li *ngFor="let file of uploadedFiles">{{ file.name }} - {{ file.size }} bytes</li>
                            </ul>
                        </ng-template>
                    </p-fileupload>
                </div>
            </div>
            <div class="col-span-full lg:col-span-6">
                <div class="card">
                    <div class="font-semibold text-xl mb-4">Basic</div>
                    <div class="flex flex-col gap-4 items-center justify-center">
                        <p-fileupload #fu mode="basic" chooseLabel="Choose" chooseIcon="pi pi-upload" name="demo[]" url="https://www.primefaces.org/cdn/api/upload.php" accept="image/*" maxFileSize="1000000" (onUpload)="onUpload($event)" />
                        <p-button label="Upload" (onClick)="fu.upload()" severity="secondary" />
                    </div>
                </div>
            </div>
        </div>`,
    providers: [MessageService],
})
export class FileDemo {
    uploadedFiles: any[] = []

    constructor(private messageService: MessageService) {
    }

    onUpload(event: any) {
        for (const file of event.files) {
            this.uploadedFiles.push(file)
        }

        this.messageService.add({ severity: 'info', summary: 'Success', detail: 'File Uploaded' })
    }

    onBasicUpload() {
        this.messageService.add({ severity: 'info', summary: 'Success', detail: 'File Uploaded with Basic Mode' })
    }
}
