import { ComponentFixture, TestBed } from '@angular/core/testing';

import { GenericListComponent } from './generic-list.component';

describe('GenericListComponent', () => {
  let component: GenericListComponent;
  let fixture: ComponentFixture<GenericListComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ GenericListComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(GenericListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
