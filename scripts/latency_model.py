from abc import ABC, abstractmethod
import yaml
from scipy.stats import nct
import math
import functools


class LatencyModelConfig(object):
    def __init__(self, modelDict):
        for key in modelDict:
            if isinstance(modelDict[key], dict):
                modelDict[key] = LatencyModelConfig(modelDict[key])
        self.__dict__.update(modelDict)


class LatencyModel(ABC):
    def __init__(self, configFilePath):
        self.configFilePath = configFilePath
        self.bytesWritten = 0
        self.latencyModelConfig = None
        self.loadLatencyModelConfig()


    @abstractmethod
    def calculateLatency(self, writeSize):
        pass

    def applyWrite(self, writeSize):
        latency = self.calculateLatency(writeSize)
        self.bytesWritten += writeSize
        return latency

    def reset(self):
        self.bytesWritten = 0

    def loadLatencyModelConfig(self):
        with open(self.configFilePath) as model_file:
            model_dict = yaml.load(model_file, Loader=yaml.FullLoader)
            self.latencyModelConfig = LatencyModelConfig(model_dict)


class LatencyModel4K(LatencyModel):
    def calculateLatency(self, writeSize):
        if writeSize == 0:
            return 0
        writesApplied = self.bytesWritten / float(self.latencyModelConfig.writeSize)
        # Request size-dependent component
        runLen = writeSize / float(self.latencyModelConfig.writeSize)
        compactLat = 0
        if writesApplied // self.latencyModelConfig.compaction.l0.frequency != (
                writesApplied + runLen) // self.latencyModelConfig.compaction.l0.frequency:
            # L0 Compaction
            compactLat += self.latencyModelConfig.compaction.l0.duration
            print('L0 Compaction')

        if writesApplied // self.latencyModelConfig.compaction.l1.frequency != (
                writesApplied + runLen) // self.latencyModelConfig.compaction.l1.frequency:
            # Other levels Compaction
            compactLat += self.latencyModelConfig.compaction.l1.duration
            print('L1 Compaction')

        if writesApplied // self.latencyModelConfig.compaction.otherLevels.frequency != (
                writesApplied + runLen) // self.latencyModelConfig.compaction.otherLevels.frequency:
            # Other levels Compaction
            compactLat += self.latencyModelConfig.compaction.otherLevels.duration
            print('L > 1 Compaction')

        # not affected write latency distribution
        latencies = nct.rvs(self.latencyModelConfig.writeDistribution.df, self.latencyModelConfig.writeDistribution.nc,
                            loc=self.latencyModelConfig.writeDistribution.loc, scale=self.latencyModelConfig.writeDistribution.scale,
                            size=math.ceil(runLen))
        latencies = list(map(lambda a: abs(a * 1_000_000), latencies))  # to micro seconds
        pureWriteLatency = functools.reduce(lambda a, b: a + b, latencies)
        return pureWriteLatency + compactLat
