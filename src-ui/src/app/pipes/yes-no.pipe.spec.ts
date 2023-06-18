import { YesNoPipe } from './yes-no.pipe'

describe('YesNoPipe', () => {
  it('should convert booleans to yes / no', () => {
    const pipe = new YesNoPipe()
    expect(pipe.transform(true)).toEqual('Yes')
    expect(pipe.transform(false)).toEqual('No')
  })
})
