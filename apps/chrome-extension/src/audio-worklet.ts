interface AudioWorkletProcessorPort {
  postMessage(message: Float32Array, transfer: Transferable[]): void;
}

declare const AudioWorkletProcessor: {
  new (): {
    readonly port: AudioWorkletProcessorPort;
  };
};

declare function registerProcessor(
  name: string,
  processorConstructor: new () => {
    process(
      inputs: Float32Array[][],
      outputs: Float32Array[][],
      parameters: Record<string, Float32Array>,
    ): boolean;
  },
): void;

class SubmarineCaptureProcessor extends AudioWorkletProcessor {
  public process(inputs: Float32Array[][]): boolean {
    const input = inputs[0]?.[0];
    if (input !== undefined && input.length > 0) {
      const copy = input.slice();
      this.port.postMessage(copy, [copy.buffer]);
    }
    return true;
  }
}

registerProcessor("submarine-capture", SubmarineCaptureProcessor);
