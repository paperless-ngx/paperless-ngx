import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UploadLargeFileComponent } from './upload-large-file.component';

describe('UploadLargeFileComponent', () => {
  let component: UploadLargeFileComponent;
  let fixture: ComponentFixture<UploadLargeFileComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ UploadLargeFileComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(UploadLargeFileComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
